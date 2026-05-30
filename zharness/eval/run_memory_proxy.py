"""Run API-only in-context trace-memory proxy evaluations for MiniLang."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

from dotenv import load_dotenv

from zharness.agents.llm_agent import MiniLangLLMAgent, mock_agent_run
from zharness.envs.minilang.generator import Episode, make_episode
from zharness.envs.minilang.verifier import verify_answers
from zharness.eval.cli_utils import parse_extra_body_json
from zharness.eval.minilang_splits import TRANSFORMS, make_target_episode, parse_csv
from zharness.eval.trace_memory import TRACE_VARIANTS, build_trace_text, scan_trace_for_leakage


REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_VARIANTS = ("none",) + TRACE_VARIANTS


def _load_repo_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


async def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    _load_repo_env()
    transforms = parse_csv(args.transforms, TRANSFORMS)
    variants = parse_csv(args.memory_variants, MEMORY_VARIANTS)
    output_dir = _make_output_dir(args.output_dir)

    agent: Optional[MiniLangLLMAgent] = None
    if args.mock_policy is None:
        agent = MiniLangLLMAgent(
            client_name=args.client,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            api_key_env=args.api_key_env,
            base_url_env=args.base_url_env,
            reasoning_effort=args.reasoning_effort,
            extra_body=parse_extra_body_json(args.extra_body_json),
        )

    records: List[Dict[str, object]] = []
    try:
        for episode_index in range(args.episodes):
            seed = args.seed + episode_index
            source_episode = make_episode(
                seed,
                support_budget=args.support_budget,
                parse_tasks=args.parse_tasks,
                generate_tasks=args.generate_tasks,
                difficulty=args.difficulty,
            )
            for transform_name in transforms:
                target_episode = make_target_episode(source_episode, transform_name, seed)
                for variant in variants:
                    record = await _run_one_variant(
                        source_episode=source_episode,
                        target_episode=target_episode,
                        transform_name=transform_name,
                        variant=variant,
                        agent=agent,
                        mock_policy=args.mock_policy,
                        max_retries=args.max_retries,
                    )
                    records.append(record)
                    _append_jsonl(output_dir / "records.jsonl", record)
                    _print_record(record)
    finally:
        if agent is not None:
            await agent.aclose()

    summary = _summarize(records)
    payload = {
        "config": vars(args),
        "summary": summary,
        "num_records": len(records),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote memory proxy artifacts to {output_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return payload


async def _run_one_variant(
    *,
    source_episode: Episode,
    target_episode: Episode,
    transform_name: str,
    variant: str,
    agent: Optional[MiniLangLLMAgent],
    mock_policy: Optional[str],
    max_retries: int,
) -> Dict[str, object]:
    errors: List[str] = []
    agent_run = None
    memory_text = "" if variant == "none" else build_trace_text(source_episode, variant)
    leakage_scan = {"passed": True, "num_violations": 0, "violations": []}
    if variant != "none":
        leakage_scan = scan_trace_for_leakage(source_episode, memory_text)

    if mock_policy is not None:
        agent_run = mock_agent_run(target_episode, policy=mock_policy)
    elif agent is None:
        errors.append("ValueError('agent is not initialized')")
    else:
        prompt = build_memory_prompt(target_episode, variant, memory_text)
        for _attempt in range(max_retries + 1):
            try:
                agent_run = await agent.solve_prompt(prompt)
                break
            except Exception as exc:
                errors.append(repr(exc))

    if agent_run is None:
        agent_run = mock_agent_run(target_episode, policy="empty")

    verification = verify_answers(target_episode.world, target_episode.tasks, agent_run.answers)
    metrics = verification.to_metrics()
    return {
        "source_episode_id": source_episode.episode_id,
        "target_episode_id": target_episode.episode_id,
        "source_family_id": source_episode.world.family_id,
        "target_family_id": target_episode.world.family_id,
        "transform": transform_name,
        "memory_variant": variant,
        "memory_leakage_scan": leakage_scan,
        "metrics": metrics,
        "usage": agent_run.usage,
        "model": agent_run.model,
        "error": " | ".join(errors) if errors else None,
        "attempts": len(errors) + 1 if errors else 1,
        "answers": agent_run.answers,
        "raw_response": agent_run.raw_response,
        "task_results": [asdict(result) for result in verification.task_results],
    }


def build_memory_prompt(target_episode: Episode, variant: str, memory_text: str) -> str:
    sections = [
        "You are solving one MiniLang episode.",
        "MiniLang commands map to JSON meanings with fields: action, object, color, count, neg.",
        "Use the current episode's visible examples as the authority.",
        "A previous trace-memory artifact may be available. It may be stale or task-specific; use only reusable strategy unless current evidence supports it.",
        "Visible examples:",
        *[f"- {example.to_prompt()}" for example in target_episode.examples],
    ]
    if variant != "none":
        sections.extend(
            [
                "",
                f"Trace-memory artifact variant: {variant}",
                memory_text,
            ]
        )
    sections.extend(
        [
            "",
            "Tasks:",
            *[f"- {task.to_prompt()}" for task in target_episode.tasks],
            "",
            "Return this JSON schema exactly:",
            '{"answers":[{"task_id":"p0","meaning":{"action":"jump","object":"door","color":"red","count":2,"neg":false}},{"task_id":"g0","command":"dak mip"}]}',
        ]
    )
    return "\n".join(sections)


def _summarize(records: List[Dict[str, object]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, object]]]] = {}
    for record in records:
        transform_name = str(record["transform"])
        variant = str(record["memory_variant"])
        grouped.setdefault(transform_name, {}).setdefault(variant, []).append(record)

    summary: Dict[str, Dict[str, Dict[str, float]]] = {}
    for transform_name, by_variant in grouped.items():
        summary[transform_name] = {}
        for variant, matching_records in by_variant.items():
            metrics = [record["metrics"] for record in matching_records]
            summary[transform_name][variant] = {
                "n": len(matching_records),
                "accuracy": mean(metric["accuracy"] for metric in metrics),
                "parse_accuracy": mean(metric["parse_accuracy"] for metric in metrics),
                "generate_accuracy": mean(metric["generate_accuracy"] for metric in metrics),
                "total_tokens": sum(
                    int(record.get("usage", {}).get("total_tokens", 0) or 0)
                    for record in matching_records
                ),
                "avg_total_tokens": mean(
                    int(record.get("usage", {}).get("total_tokens", 0) or 0)
                    for record in matching_records
                ),
                "errors": sum(1 for record in matching_records if record.get("error")),
                "memory_leakage_pass_rate": mean(
                    1.0 if record["memory_leakage_scan"]["passed"] else 0.0
                    for record in matching_records
                ),
            }
    return summary


def _make_output_dir(raw_output_dir: Optional[str]) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "minilang_memory_proxy" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_record(record: Dict[str, object]) -> None:
    metrics = record["metrics"]
    error_marker = " ERROR" if record.get("error") else ""
    print(
        f"{record['source_episode_id']} {record['transform']:<17s} {record['memory_variant']:<18s} "
        f"acc={metrics['accuracy']:.3f} parse={metrics['parse_accuracy']:.3f} "
        f"gen={metrics['generate_accuracy']:.3f}{error_marker}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--support-budget", type=int, default=8)
    parser.add_argument("--parse-tasks", type=int, default=4)
    parser.add_argument("--generate-tasks", type=int, default=4)
    parser.add_argument("--difficulty", choices=("basic", "hard"), default="hard")
    parser.add_argument("--transforms", default="renamed_vocab,composition_swap,heldout_family")
    parser.add_argument("--memory-variants", default="none,raw,stripped,artifact_scrubbed")
    parser.add_argument("--client", default="openrouter_newapi")
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--api-key-env", default="apihy_API_KEY_deepseek")
    parser.add_argument("--base-url-env", default="apihy_BASE_URL")
    parser.add_argument("--reasoning-effort", default="none")
    parser.add_argument("--extra-body-json", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--mock-policy", choices=("oracle", "empty"), default=None)
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()

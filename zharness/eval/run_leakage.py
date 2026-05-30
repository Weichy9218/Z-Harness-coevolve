"""Run MiniLang counterfactual leakage tests.

The key comparison is:

- source_raw_k_spec: target examples/tasks, but the source world's rulebook.
- target_scaffold_k_spec: target examples/tasks and target world's rulebook.

If source_raw stays high under renamed/order-swap transforms, the task leaks or
the transform is too weak. If target_scaffold recovers, the verifier and target
scaffold are working.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path
import random
from statistics import mean
from typing import Dict, List, Optional

from dotenv import load_dotenv

from zharness.agents.llm_agent import MiniLangLLMAgent, mock_agent_run
from zharness.agents.prompts import CONDITION_K_SPEC
from zharness.envs.minilang.generator import Episode, make_episode, make_tasks, support_examples
from zharness.envs.minilang.transforms import order_swap_world, renamed_vocab_world
from zharness.envs.minilang.verifier import verify_answers
from zharness.eval.cli_utils import parse_extra_body_json


REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSFORMS = ("same_world", "renamed_vocab", "order_swap")
ARMS = ("source_raw_k_spec", "target_scaffold_k_spec")


def _load_repo_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


async def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    _load_repo_env()
    transforms = _parse_csv(args.transforms, TRANSFORMS)
    arms = _parse_csv(args.arms, ARMS)
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
                target_episode = _target_episode(source_episode, transform_name, seed)
                for arm in arms:
                    record = await _run_one_arm(
                        source_episode=source_episode,
                        target_episode=target_episode,
                        transform_name=transform_name,
                        arm=arm,
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
    print(f"\nWrote run artifacts to {output_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return payload


async def _run_one_arm(
    *,
    source_episode: Episode,
    target_episode: Episode,
    transform_name: str,
    arm: str,
    agent: Optional[MiniLangLLMAgent],
    mock_policy: Optional[str],
    max_retries: int,
) -> Dict[str, object]:
    errors: List[str] = []
    agent_run = None
    override_rulebook = None
    if arm == "source_raw_k_spec":
        override_rulebook = source_episode.world.rulebook_text()
    elif arm == "target_scaffold_k_spec":
        override_rulebook = target_episode.world.rulebook_text()
    else:
        raise ValueError(f"unknown arm: {arm}")

    if mock_policy is not None:
        agent_run = mock_agent_run(target_episode, policy=mock_policy)
    elif agent is None:
        errors.append("ValueError('agent is not initialized')")
    else:
        for _attempt in range(max_retries + 1):
            try:
                agent_run = await agent.solve(
                    target_episode,
                    CONDITION_K_SPEC,
                    override_rulebook=override_rulebook,
                )
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
        "arm": arm,
        "metrics": metrics,
        "usage": agent_run.usage,
        "model": agent_run.model,
        "error": " | ".join(errors) if errors else None,
        "attempts": len(errors) + 1 if errors else 1,
        "answers": agent_run.answers,
        "raw_response": agent_run.raw_response,
        "task_results": [asdict(result) for result in verification.task_results],
    }


def _target_episode(source_episode: Episode, transform_name: str, seed: int) -> Episode:
    source_world = source_episode.world
    if transform_name == "same_world":
        target_world = source_world
    elif transform_name == "renamed_vocab":
        target_world = renamed_vocab_world(source_world, random.Random(seed + 30_000))
    elif transform_name == "order_swap":
        target_world = order_swap_world(source_world)
    else:
        raise ValueError(f"unknown transform: {transform_name}")

    if target_world is source_world:
        return source_episode

    return replace(
        source_episode,
        episode_id=f"{source_episode.episode_id}-{transform_name}",
        world=target_world,
        examples=support_examples(target_world, random.Random(seed + 10_000), len(source_episode.examples)),
        tasks=make_tasks(
            target_world,
            random.Random(seed + 20_000),
            _count_kind(source_episode, "parse"),
            _count_kind(source_episode, "generate"),
        ),
    )


def _count_kind(episode: Episode, kind: str) -> int:
    return sum(1 for task in episode.tasks if task.kind == kind)


def _summarize(records: List[Dict[str, object]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, float]]]] = {}
    for record in records:
        transform_name = str(record["transform"])
        arm = str(record["arm"])
        grouped.setdefault(transform_name, {}).setdefault(arm, []).append(record["metrics"])

    summary: Dict[str, Dict[str, Dict[str, float]]] = {}
    for transform_name, by_arm in grouped.items():
        summary[transform_name] = {}
        for arm, metrics in by_arm.items():
            matching_records = [
                record
                for record in records
                if record["transform"] == transform_name and record["arm"] == arm
            ]
            summary[transform_name][arm] = {
                "accuracy": mean(metric["accuracy"] for metric in metrics),
                "parse_accuracy": mean(metric["parse_accuracy"] for metric in metrics),
                "generate_accuracy": mean(metric["generate_accuracy"] for metric in metrics),
                "total_tokens": sum(
                    int(record.get("usage", {}).get("total_tokens", 0) or 0)
                    for record in matching_records
                ),
                "errors": sum(1 for record in matching_records if record.get("error")),
            }
    return summary


def _parse_csv(raw: str, allowed: tuple[str, ...]) -> List[str]:
    values: List[str] = []
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        if item not in allowed:
            raise ValueError(f"unknown value '{item}'. Allowed: {', '.join(allowed)}")
        values.append(item)
    return values


def _make_output_dir(raw_output_dir: Optional[str]) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "minilang_leakage" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_record(record: Dict[str, object]) -> None:
    metrics = record["metrics"]
    error_marker = " ERROR" if record.get("error") else ""
    print(
        f"{record['source_episode_id']} {record['transform']:<13s} {record['arm']:<22s} "
        f"acc={metrics['accuracy']:.3f} "
        f"parse={metrics['parse_accuracy']:.3f} "
        f"gen={metrics['generate_accuracy']:.3f}{error_marker}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--support-budget", type=int, default=8)
    parser.add_argument("--parse-tasks", type=int, default=4)
    parser.add_argument("--generate-tasks", type=int, default=4)
    parser.add_argument("--difficulty", choices=("basic", "hard"), default="hard")
    parser.add_argument("--transforms", default="renamed_vocab,order_swap")
    parser.add_argument("--arms", default=",".join(ARMS))
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

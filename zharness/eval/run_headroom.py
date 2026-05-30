"""Run the MiniLang scaffold-headroom experiment with API or mock policies."""

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
from zharness.agents.prompts import CONDITIONS, parse_conditions
from zharness.envs.minilang.generator import make_episode
from zharness.envs.minilang.verifier import verify_answers


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_repo_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


async def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    _load_repo_env()
    conditions = list(parse_conditions(args.conditions))
    output_dir = _make_output_dir(args.output_dir)

    agent: Optional[MiniLangLLMAgent] = None
    if args.mock_policy is None:
        agent = MiniLangLLMAgent(
            client_name=args.client,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )

    records: List[Dict[str, object]] = []
    try:
        for episode_index in range(args.episodes):
            seed = args.seed + episode_index
            episode = make_episode(
                seed,
                support_budget=args.support_budget,
                parse_tasks=args.parse_tasks,
                generate_tasks=args.generate_tasks,
            )
            for condition in conditions:
                record = await _run_one_condition(
                    episode=episode,
                    condition=condition,
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
    summary_payload = {
        "config": vars(args),
        "summary": summary,
        "num_records": len(records),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote run artifacts to {output_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary_payload


async def _run_one_condition(
    *,
    episode,
    condition: str,
    agent: Optional[MiniLangLLMAgent],
    mock_policy: Optional[str],
    max_retries: int,
) -> Dict[str, object]:
    errors: List[str] = []
    agent_run = None
    if mock_policy is not None:
        agent_run = mock_agent_run(episode, policy=mock_policy)
    elif agent is None:
        errors.append("ValueError('agent is not initialized')")
    else:
        for _attempt in range(max_retries + 1):
            try:
                agent_run = await agent.solve(episode, condition)
                break
            except Exception as exc:  # keep long sweeps resumable and inspectable
                errors.append(repr(exc))

    if agent_run is None:
        agent_run = mock_agent_run(episode, policy="empty")

    verification = verify_answers(episode.world, episode.tasks, agent_run.answers)
    metrics = verification.to_metrics()
    return {
        "episode_id": episode.episode_id,
        "family_id": episode.world.family_id,
        "condition": condition,
        "metrics": metrics,
        "usage": agent_run.usage,
        "model": agent_run.model,
        "error": " | ".join(errors) if errors else None,
        "attempts": len(errors) + 1 if errors else 1,
        "answers": agent_run.answers,
        "raw_response": agent_run.raw_response,
        "task_results": [asdict(result) for result in verification.task_results],
    }


def _summarize(records: List[Dict[str, object]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[Dict[str, float]]] = {}
    for record in records:
        condition = str(record["condition"])
        grouped.setdefault(condition, []).append(record["metrics"])

    summary: Dict[str, Dict[str, float]] = {}
    for condition, metrics in grouped.items():
        summary[condition] = {
            "accuracy": mean(metric["accuracy"] for metric in metrics),
            "parse_accuracy": mean(metric["parse_accuracy"] for metric in metrics),
            "generate_accuracy": mean(metric["generate_accuracy"] for metric in metrics),
            "total_tokens": sum(
                int(record.get("usage", {}).get("total_tokens", 0) or 0)
                for record in records
                if record["condition"] == condition
            ),
            "errors": sum(1 for record in records if record["condition"] == condition and record.get("error")),
        }
    return summary


def _make_output_dir(raw_output_dir: Optional[str]) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "minilang_headroom" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_record(record: Dict[str, object]) -> None:
    metrics = record["metrics"]
    error_marker = " ERROR" if record.get("error") else ""
    print(
        f"{record['episode_id']} {record['condition']:<13s} "
        f"acc={metrics['accuracy']:.3f} "
        f"parse={metrics['parse_accuracy']:.3f} "
        f"gen={metrics['generate_accuracy']:.3f}{error_marker}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--support-budget", type=int, default=12)
    parser.add_argument("--parse-tasks", type=int, default=4)
    parser.add_argument("--generate-tasks", type=int, default=4)
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--client", default="gpt_sub2api")
    parser.add_argument("--model", default="gpt-5.4")
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

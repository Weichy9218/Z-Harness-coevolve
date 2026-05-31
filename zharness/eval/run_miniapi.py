"""Run deterministic MiniAPI no-GPU harness probes."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence, Tuple

from zharness.envs.miniapi import (
    APICall,
    MiniAPIEpisode,
    diagnostic_probe_plan,
    execute_plan,
    make_counterfactual_world,
    make_episode,
    naive_plan,
    oracle_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONDITIONS = ("no_scaffold", "k_spec", "k_gen_exec", "source_raw", "target_scaffold")


def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    conditions = list(_parse_conditions(args.conditions))
    output_dir = _make_output_dir(args.output_dir)
    records: List[Dict[str, object]] = []

    for episode_index in range(args.episodes):
        episode = make_episode(args.seed + episode_index)
        for condition in conditions:
            record = _run_one_condition(episode, condition)
            records.append(record)
            _append_jsonl(output_dir / "records.jsonl", record)
            _print_record(record)

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


def _run_one_condition(episode: MiniAPIEpisode, condition: str) -> Dict[str, object]:
    plan, scaffold_costs, action_trace = _plan_for_condition(episode, condition)
    verification = execute_plan(episode.world, episode.goal, plan)
    metrics = verification.to_metrics()

    return {
        "episode_id": episode.episode_id,
        "family_id": episode.world.family_id,
        "condition": condition,
        "goal": episode.goal.to_dict(),
        "world": asdict(episode.world),
        "metrics": metrics,
        "scaffold_costs": scaffold_costs,
        "plan": [call.to_dict() for call in plan],
        "action_trace": action_trace,
        "verifier": {
            "success": verification.success,
            "errors": list(verification.errors),
            "final_state": verification.final_state,
            "trace": list(verification.trace),
        },
    }


def _plan_for_condition(
    episode: MiniAPIEpisode,
    condition: str,
) -> Tuple[List[APICall], Dict[str, int], List[Dict[str, object]]]:
    if condition == "no_scaffold":
        return naive_plan(episode.goal), {"query_calls": 0, "verifier_calls": 0}, []

    if condition == "k_spec":
        return oracle_plan(episode.world, episode.goal), {"query_calls": 0, "verifier_calls": 0}, []

    if condition in {"k_gen_exec", "target_scaffold"}:
        plan, probe_trace = diagnostic_probe_plan(episode.world, episode.goal)
        costs = {
            "query_calls": len(probe_trace),
            "verifier_calls": len(probe_trace),
            "direct_target_query_violations": _direct_target_query_violations(episode, probe_trace),
        }
        return plan, costs, probe_trace

    if condition == "source_raw":
        source_world = make_counterfactual_world(episode.world)
        return (
            oracle_plan(source_world, episode.goal),
            {
                "query_calls": 0,
                "verifier_calls": 0,
                "source_world_counterfactual": 1,
            },
            [{"source_world": asdict(source_world)}],
        )

    raise ValueError(f"unknown MiniAPI condition: {condition}")


def _summarize(records: Sequence[Dict[str, object]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[Dict[str, float]]] = {}
    for record in records:
        grouped.setdefault(str(record["condition"]), []).append(record["metrics"])

    summary: Dict[str, Dict[str, float]] = {}
    for condition, metrics in grouped.items():
        condition_records = [record for record in records if record["condition"] == condition]
        summary[condition] = {
            "success": mean(metric["success"] for metric in metrics),
            "completion": mean(metric["completion"] for metric in metrics),
            "robustness": mean(metric["robustness"] for metric in metrics),
            "tool_use": mean(metric["tool_use"] for metric in metrics),
            "forbidden_action_rate": mean(metric["forbidden_action_rate"] for metric in metrics),
            "query_calls": sum(
                int(record.get("scaffold_costs", {}).get("query_calls", 0) or 0)
                for record in condition_records
            ),
            "verifier_calls": sum(
                int(record.get("scaffold_costs", {}).get("verifier_calls", 0) or 0)
                for record in condition_records
            ),
            "direct_target_query_violations": sum(
                int(record.get("scaffold_costs", {}).get("direct_target_query_violations", 0) or 0)
                for record in condition_records
            ),
        }
    return summary


def _direct_target_query_violations(episode: MiniAPIEpisode, probe_trace: Sequence[Dict[str, object]]) -> int:
    target_order_id = episode.goal.order_id
    return sum(1 for probe in probe_trace if str(probe.get("probe_id")) == target_order_id)


def _parse_conditions(raw: str) -> Sequence[str]:
    conditions = []
    for item in str(raw or "").split(","):
        condition = item.strip()
        if not condition:
            continue
        if condition not in CONDITIONS:
            known = ", ".join(CONDITIONS)
            raise ValueError(f"unknown condition '{condition}'. Known: {known}")
        conditions.append(condition)
    return conditions


def _make_output_dir(raw_output_dir: str | None) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "miniapi" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_record(record: Dict[str, object]) -> None:
    metrics = record["metrics"]
    costs = record.get("scaffold_costs", {})
    print(
        f"{record['episode_id']} {record['condition']:<15s} "
        f"success={metrics['success']:.0f} "
        f"completion={metrics['completion']:.3f} "
        f"robustness={metrics['robustness']:.3f} "
        f"tool={metrics['tool_use']:.3f} "
        f"q={int(costs.get('query_calls', 0) or 0)} "
        f"v={int(costs.get('verifier_calls', 0) or 0)}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    run_experiment(build_parser().parse_args())


if __name__ == "__main__":
    main()

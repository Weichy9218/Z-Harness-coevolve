"""Run deterministic MiniAPI trace-memory proxy evaluations."""

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
    make_episode,
    naive_plan,
    oracle_plan,
)
from zharness.eval.miniapi_splits import MINIAPI_TRANSFORMS, make_miniapi_target_episode, parse_csv
from zharness.eval.miniapi_trace_memory import (
    MINIAPI_TRACE_VARIANTS,
    build_miniapi_trace_text,
    scan_miniapi_trace_for_leakage,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_VARIANTS = ("none",) + MINIAPI_TRACE_VARIANTS


def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    transforms = parse_csv(args.transforms, MINIAPI_TRANSFORMS)
    variants = parse_csv(args.memory_variants, MEMORY_VARIANTS)
    output_dir = _make_output_dir(args.output_dir)
    records: List[Dict[str, object]] = []

    for episode_index in range(args.episodes):
        seed = args.seed + episode_index
        source_episode = make_episode(seed)
        for transform_name in transforms:
            target_episode = make_miniapi_target_episode(source_episode, transform_name, seed)
            for variant in variants:
                record = _run_one_variant(
                    source_episode=source_episode,
                    target_episode=target_episode,
                    transform_name=transform_name,
                    variant=variant,
                )
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
    print(f"\nWrote MiniAPI memory proxy artifacts to {output_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return payload


def _run_one_variant(
    *,
    source_episode: MiniAPIEpisode,
    target_episode: MiniAPIEpisode,
    transform_name: str,
    variant: str,
) -> Dict[str, object]:
    plan, scaffold_costs, action_trace = _plan_for_memory_variant(source_episode, target_episode, variant)
    result = execute_plan(target_episode.world, target_episode.goal, plan)
    metrics = result.to_metrics()

    memory_text = "" if variant == "none" else build_miniapi_trace_text(source_episode, variant)
    leakage_scan = {"passed": True, "num_violations": 0, "violations": []}
    if variant != "none":
        leakage_scan = scan_miniapi_trace_for_leakage(source_episode, memory_text)

    return {
        "source_episode_id": source_episode.episode_id,
        "target_episode_id": target_episode.episode_id,
        "source_family_id": source_episode.world.family_id,
        "target_family_id": target_episode.world.family_id,
        "transform": transform_name,
        "memory_variant": variant,
        "memory_leakage_scan": leakage_scan,
        "metrics": metrics,
        "scaffold_costs": scaffold_costs,
        "plan": [call.to_dict() for call in plan],
        "action_trace": action_trace,
        "verifier": {
            "success": result.success,
            "errors": list(result.errors),
            "final_state": result.final_state,
            "trace": list(result.trace),
        },
    }


def _plan_for_memory_variant(
    source_episode: MiniAPIEpisode,
    target_episode: MiniAPIEpisode,
    variant: str,
) -> Tuple[List[APICall], Dict[str, int], List[Dict[str, object]]]:
    if variant == "none":
        return naive_plan(target_episode.goal), {"query_calls": 0, "verifier_calls": 0}, []

    if variant == "raw":
        return (
            oracle_plan(source_episode.world, target_episode.goal),
            {"query_calls": 0, "verifier_calls": 0, "source_profile_reuse": 1},
            [{"source_world": asdict(source_episode.world)}],
        )

    if variant in {"action_stripped", "artifact_scrubbed_action"}:
        plan, probe_trace = diagnostic_probe_plan(target_episode.world, target_episode.goal)
        costs = {
            "query_calls": len(probe_trace),
            "verifier_calls": len(probe_trace),
            "direct_target_query_violations": _direct_target_query_violations(target_episode, probe_trace),
        }
        return plan, costs, probe_trace

    if variant == "artifact_scrubbed":
        return _generic_safe_plan(target_episode.goal), {"query_calls": 0, "verifier_calls": 0}, []

    raise ValueError(f"unknown MiniAPI memory variant: {variant}")


def _generic_safe_plan(goal) -> List[APICall]:
    calls = naive_plan(goal)
    return [APICall("authenticate", {"token": goal.auth_token})] + calls


def _summarize(records: Sequence[Dict[str, object]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, object]]]] = {}
    for record in records:
        grouped.setdefault(str(record["transform"]), {}).setdefault(str(record["memory_variant"]), []).append(record)

    summary: Dict[str, Dict[str, Dict[str, float]]] = {}
    for transform_name, by_variant in grouped.items():
        summary[transform_name] = {}
        for variant, matching_records in by_variant.items():
            metrics = [record["metrics"] for record in matching_records]
            summary[transform_name][variant] = {
                "n": len(matching_records),
                "success": mean(metric["success"] for metric in metrics),
                "completion": mean(metric["completion"] for metric in metrics),
                "robustness": mean(metric["robustness"] for metric in metrics),
                "tool_use": mean(metric["tool_use"] for metric in metrics),
                "forbidden_action_rate": mean(metric["forbidden_action_rate"] for metric in metrics),
                "query_calls": sum(
                    int(record.get("scaffold_costs", {}).get("query_calls", 0) or 0)
                    for record in matching_records
                ),
                "verifier_calls": sum(
                    int(record.get("scaffold_costs", {}).get("verifier_calls", 0) or 0)
                    for record in matching_records
                ),
                "memory_leakage_pass_rate": mean(
                    1.0 if record["memory_leakage_scan"]["passed"] else 0.0
                    for record in matching_records
                ),
            }
    return summary


def _direct_target_query_violations(episode: MiniAPIEpisode, probe_trace: Sequence[Dict[str, object]]) -> int:
    return sum(1 for probe in probe_trace if str(probe.get("probe_id")) == episode.goal.order_id)


def _make_output_dir(raw_output_dir: str | None) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "miniapi_memory_proxy" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_record(record: Dict[str, object]) -> None:
    metrics = record["metrics"]
    costs = record.get("scaffold_costs", {})
    print(
        f"{record['source_episode_id']} {record['transform']:<20s} {record['memory_variant']:<24s} "
        f"success={metrics['success']:.0f} completion={metrics['completion']:.3f} "
        f"q={int(costs.get('query_calls', 0) or 0)} v={int(costs.get('verifier_calls', 0) or 0)}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--transforms", default="same_world,counterfactual_world,heldout_world")
    parser.add_argument(
        "--memory-variants",
        default="none,raw,action_stripped,artifact_scrubbed,artifact_scrubbed_action",
    )
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    run_experiment(build_parser().parse_args())


if __name__ == "__main__":
    main()

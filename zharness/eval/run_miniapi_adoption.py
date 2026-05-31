"""Run deterministic MiniAPI skill adoption and removal ablations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence, Tuple

from zharness.envs.miniapi import (
    APICall,
    APIWorld,
    MiniAPIEpisode,
    MiniAPIGoal,
    diagnostic_probe_plan,
    execute_plan,
    make_episode,
    oracle_plan,
)
from zharness.eval.miniapi_splits import MINIAPI_TRANSFORMS, make_miniapi_target_episode, parse_csv


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class MiniAPISkill:
    skill_id: str
    description: str


SKILLS = (
    MiniAPISkill("kg_auth_first", "Authenticate before any state-changing tool call."),
    MiniAPISkill("kg_probe_hidden_profile", "Use non-target probe orders to infer hidden API ordering constraints."),
    MiniAPISkill("kspec_source_profile", "Reuse the previous episode's concrete hidden API profile."),
    MiniAPISkill("trap_skip_receipt", "Skip receipt sending because payment success is enough to ship."),
)


def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    transforms = parse_csv(args.transforms, MINIAPI_TRANSFORMS)
    output_dir = _make_output_dir(args.output_dir)
    records: List[Dict[str, object]] = []

    for episode_index in range(args.episodes):
        seed = args.seed + episode_index
        source_episode = make_episode(seed)
        for transform_name in transforms:
            target_episode = make_miniapi_target_episode(source_episode, transform_name, seed)
            for skill in SKILLS:
                record = _run_one_skill(source_episode, target_episode, transform_name, skill)
                records.append(record)
                _append_jsonl(output_dir / "records.jsonl", record)
                _print_record(record)

    summary = _summarize(records, robust_delta_tolerance=args.robust_delta_tolerance)
    payload = {
        "config": vars(args),
        "skill_ids": [skill.skill_id for skill in SKILLS],
        "summary": summary,
        "num_records": len(records),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote MiniAPI adoption artifacts to {output_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return payload


def _run_one_skill(
    source_episode: MiniAPIEpisode,
    target_episode: MiniAPIEpisode,
    transform_name: str,
    skill: MiniAPISkill,
) -> Dict[str, object]:
    full_plan, full_costs = _plan_with_skill(skill.skill_id, source_episode.world, target_episode.world, target_episode.goal)
    removal_plan, removal_costs = _plan_without_skill(
        skill.skill_id,
        source_episode.world,
        target_episode.world,
        target_episode.goal,
    )
    full_result = execute_plan(target_episode.world, target_episode.goal, full_plan)
    removal_result = execute_plan(target_episode.world, target_episode.goal, removal_plan)

    full_metrics = full_result.to_metrics()
    removal_metrics = removal_result.to_metrics()
    accuracy_delta = full_metrics["success"] - removal_metrics["success"]

    return {
        "source_episode_id": source_episode.episode_id,
        "target_episode_id": target_episode.episode_id,
        "source_family_id": source_episode.world.family_id,
        "target_family_id": target_episode.world.family_id,
        "transform": transform_name,
        "skill_id": skill.skill_id,
        "description": skill.description,
        "full_metrics": full_metrics,
        "removal_metrics": removal_metrics,
        "accuracy_delta": accuracy_delta,
        "full_costs": full_costs,
        "removal_costs": removal_costs,
        "full_errors": list(full_result.errors),
        "removal_errors": list(removal_result.errors),
        "called": _called_by_naive_adoption(skill.skill_id, transform_name, accuracy_delta),
    }


def _plan_with_skill(
    skill_id: str,
    source_world: APIWorld,
    target_world: APIWorld,
    goal: MiniAPIGoal,
) -> Tuple[List[APICall], Dict[str, int]]:
    if skill_id == "kg_auth_first":
        return oracle_plan(target_world, goal), {"query_calls": 0, "verifier_calls": 0}

    if skill_id == "kg_probe_hidden_profile":
        plan, probe_trace = diagnostic_probe_plan(target_world, goal)
        return plan, {"query_calls": len(probe_trace), "verifier_calls": len(probe_trace)}

    if skill_id == "kspec_source_profile":
        return oracle_plan(source_world, goal), {"query_calls": 0, "verifier_calls": 0, "source_profile_reuse": 1}

    if skill_id == "trap_skip_receipt":
        return _drop_calls(oracle_plan(target_world, goal), {"send_receipt"}), {"query_calls": 0, "verifier_calls": 0}

    raise ValueError(f"unknown MiniAPI skill: {skill_id}")


def _plan_without_skill(
    skill_id: str,
    source_world: APIWorld,
    target_world: APIWorld,
    goal: MiniAPIGoal,
) -> Tuple[List[APICall], Dict[str, int]]:
    if skill_id == "kg_auth_first":
        return _drop_calls(oracle_plan(target_world, goal), {"authenticate"}), {"query_calls": 0, "verifier_calls": 0}

    if skill_id == "kg_probe_hidden_profile":
        return oracle_plan(source_world, goal), {"query_calls": 0, "verifier_calls": 0, "source_profile_reuse": 1}

    if skill_id == "kspec_source_profile":
        plan, probe_trace = diagnostic_probe_plan(target_world, goal)
        return plan, {"query_calls": len(probe_trace), "verifier_calls": len(probe_trace)}

    if skill_id == "trap_skip_receipt":
        return oracle_plan(target_world, goal), {"query_calls": 0, "verifier_calls": 0}

    raise ValueError(f"unknown MiniAPI skill: {skill_id}")


def _summarize(records: Sequence[Dict[str, object]], *, robust_delta_tolerance: float) -> Dict[str, object]:
    skill_ids = [skill.skill_id for skill in SKILLS]
    adoption: Dict[str, Dict[str, float]] = {}
    for skill_id in skill_ids:
        matching = [record for record in records if record["skill_id"] == skill_id]
        called = [record for record in matching if record["called"]]
        adoption[skill_id] = {
            "call_count": len(called),
            "call_rate": len(called) / len(matching) if matching else 0.0,
            "success_when_called": mean(record["full_metrics"]["success"] for record in called) if called else 0.0,
        }
        adoption[skill_id]["adoption_score"] = (
            adoption[skill_id]["call_rate"] * adoption[skill_id]["success_when_called"]
        )

    removal_delta_by_transform: Dict[str, Dict[str, Dict[str, float]]] = {}
    for transform_name in sorted({str(record["transform"]) for record in records}):
        removal_delta_by_transform[transform_name] = {}
        for skill_id in skill_ids:
            matching = [
                float(record["accuracy_delta"])
                for record in records
                if record["transform"] == transform_name and record["skill_id"] == skill_id
            ]
            removal_delta_by_transform[transform_name][skill_id] = {
                "n": len(matching),
                "mean_accuracy_delta": mean(matching) if matching else 0.0,
            }

    return {
        "adoption": adoption,
        "removal_delta_by_transform": removal_delta_by_transform,
        "robust_adoption": _classify_robust_adoption(
            skill_ids=skill_ids,
            removal_delta_by_transform=removal_delta_by_transform,
            tolerance=robust_delta_tolerance,
            quarantine_skill_ids={"kspec_source_profile"},
        ),
        "spearman_adoption_vs_removal_delta": _spearman(
            [adoption[skill_id]["adoption_score"] for skill_id in skill_ids],
            [
                mean(
                    removal_delta_by_transform[transform][skill_id]["mean_accuracy_delta"]
                    for transform in removal_delta_by_transform
                )
                for skill_id in skill_ids
            ],
        ),
        "num_records": len(records),
    }


def _classify_robust_adoption(
    *,
    skill_ids: Sequence[str],
    removal_delta_by_transform: Dict[str, Dict[str, Dict[str, float]]],
    tolerance: float,
    quarantine_skill_ids: set[str],
) -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}
    counterfactual_transforms = [
        transform
        for transform in removal_delta_by_transform
        if transform not in {"same_world", "heldout_world"}
    ]
    for skill_id in skill_ids:
        seen_delta = _transform_delta(removal_delta_by_transform, "same_world", skill_id)
        heldout_delta = _transform_delta(removal_delta_by_transform, "heldout_world", skill_id)
        counterfactual_deltas = [
            _transform_delta(removal_delta_by_transform, transform, skill_id)
            for transform in counterfactual_transforms
            if _transform_n(removal_delta_by_transform, transform, skill_id) > 0
        ]
        counterfactual_mean = mean(counterfactual_deltas) if counterfactual_deltas else 0.0
        min_counterfactual_delta = min(counterfactual_deltas) if counterfactual_deltas else 0.0
        has_negative_transfer = min_counterfactual_delta < -tolerance or heldout_delta < -tolerance
        has_robust_positive = (
            min_counterfactual_delta >= -tolerance
            and heldout_delta >= -tolerance
            and max(counterfactual_mean, heldout_delta, seen_delta) > tolerance
        )

        if skill_id in quarantine_skill_ids:
            decision = "quarantine"
            reason = "known_source_specific_leakage"
        elif has_negative_transfer:
            decision = "quarantine"
            reason = "counterfactual_or_heldout_negative"
        elif has_robust_positive:
            decision = "promote_candidate"
            reason = "nonnegative_counterfactual_and_heldout_delta"
        else:
            decision = "reject_or_redundant"
            reason = "no_positive_removal_delta"

        result[skill_id] = {
            "decision": decision,
            "reason": reason,
            "seen_delta": seen_delta,
            "counterfactual_mean_delta": counterfactual_mean,
            "min_counterfactual_delta": min_counterfactual_delta,
            "heldout_delta": heldout_delta,
        }
    return result


def _called_by_naive_adoption(skill_id: str, transform_name: str, accuracy_delta: float) -> bool:
    if skill_id == "kspec_source_profile":
        return True
    return transform_name == "same_world" and accuracy_delta > 0.0


def _drop_calls(calls: Sequence[APICall], names: set[str]) -> List[APICall]:
    return [call for call in calls if call.name not in names]


def _transform_delta(
    removal_delta_by_transform: Dict[str, Dict[str, Dict[str, float]]],
    transform_name: str,
    skill_id: str,
) -> float:
    return float(
        removal_delta_by_transform.get(transform_name, {})
        .get(skill_id, {})
        .get("mean_accuracy_delta", 0.0)
    )


def _transform_n(
    removal_delta_by_transform: Dict[str, Dict[str, Dict[str, float]]],
    transform_name: str,
    skill_id: str,
) -> int:
    return int(removal_delta_by_transform.get(transform_name, {}).get(skill_id, {}).get("n", 0) or 0)


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    x_ranks = _ranks(xs)
    y_ranks = _ranks(ys)
    x_mean = mean(x_ranks)
    y_mean = mean(y_ranks)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks))
    x_denom = sum((x - x_mean) ** 2 for x in x_ranks) ** 0.5
    y_denom = sum((y - y_mean) ** 2 for y in y_ranks) ** 0.5
    if x_denom == 0 or y_denom == 0:
        return 0.0
    return numerator / (x_denom * y_denom)


def _ranks(values: Sequence[float]) -> List[float]:
    sorted_pairs = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(sorted_pairs):
        end = cursor + 1
        while end < len(sorted_pairs) and sorted_pairs[end][0] == sorted_pairs[cursor][0]:
            end += 1
        avg_rank = (cursor + end + 1) / 2.0
        for _, index in sorted_pairs[cursor:end]:
            ranks[index] = avg_rank
        cursor = end
    return ranks


def _make_output_dir(raw_output_dir: str | None) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "miniapi_adoption" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_record(record: Dict[str, object]) -> None:
    print(
        f"{record['source_episode_id']} {record['transform']:<20s} {record['skill_id']:<24s} "
        f"delta={record['accuracy_delta']:.3f} "
        f"full={record['full_metrics']['success']:.0f} "
        f"removed={record['removal_metrics']['success']:.0f}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--transforms", default="same_world,counterfactual_world,heldout_world")
    parser.add_argument("--robust-delta-tolerance", type=float, default=0.0)
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    run_experiment(build_parser().parse_args())


if __name__ == "__main__":
    main()

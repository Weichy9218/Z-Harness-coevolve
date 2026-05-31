"""Shared training-manifest builder and safety validator."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Dict, Iterable, List, Sequence

from zharness.envs.minilang.generator import make_episode as make_minilang_episode
from zharness.envs.miniapi import make_episode as make_miniapi_episode
from zharness.eval.miniapi_trace_memory import (
    MINIAPI_TRACE_VARIANTS,
    build_miniapi_trace_record,
)
from zharness.eval.trace_memory import TRACE_VARIANTS, build_trace_record


RAW_VARIANTS = {"raw", "raw_action"}
TRAINABLE_VARIANTS = {
    "action_stripped",
    "artifact_scrubbed_action",
}


def build_manifest_rows(
    *,
    envs: Sequence[str],
    seed: int,
    episodes: int,
    run_id: str,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for env in envs:
        if env == "minilang":
            rows.extend(_build_minilang_rows(seed=seed, episodes=episodes, run_id=run_id))
        elif env == "miniapi":
            rows.extend(_build_miniapi_rows(seed=seed, episodes=episodes, run_id=run_id))
        else:
            raise ValueError(f"unknown manifest env: {env}")
    return rows


def validate_manifest_rows(rows: Sequence[Dict[str, object]]) -> List[str]:
    errors: List[str] = []
    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or f"row-{index}")
        missing = _missing_required_fields(row)
        if missing:
            errors.append(f"{row_id}: missing required fields: {', '.join(missing)}")
            continue

        trainable = bool(row.get("trainable"))
        trace_variant = str(row.get("trace_variant", ""))
        leakage_scan = row.get("leakage_scan", {})
        robust_adoption = row.get("robust_adoption", {})
        if not isinstance(leakage_scan, dict):
            errors.append(f"{row_id}: leakage_scan must be an object")
            continue
        if not isinstance(robust_adoption, dict):
            errors.append(f"{row_id}: robust_adoption must be an object")
            continue

        if trace_variant in RAW_VARIANTS and trainable:
            errors.append(f"{row_id}: raw/source-specific trace cannot be trainable")
        if trainable and not leakage_scan.get("passed", False):
            errors.append(f"{row_id}: trainable row failed leakage scan")
        if trainable and robust_adoption.get("decision") != "promote_candidate":
            errors.append(f"{row_id}: trainable row lacks robust adoption promotion")
    return errors


def manifest_fingerprint(rows: Sequence[Dict[str, object]]) -> str:
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_manifest_jsonl(path, rows: Iterable[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _build_minilang_rows(*, seed: int, episodes: int, run_id: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for episode_index in range(episodes):
        episode = make_minilang_episode(seed + episode_index, difficulty="hard")
        for variant in TRACE_VARIANTS:
            trace_record = build_trace_record(episode, variant)
            decision = _minilang_robust_decision(variant)
            trainable = _is_trainable(trace_record["leakage_scan"], decision, variant)
            rows.append(
                _base_row(
                    run_id=run_id,
                    env="MiniLangHard",
                    split="train",
                    trace_variant=variant,
                    episode_id=episode.episode_id,
                    family_id=episode.world.family_id,
                    scaffold_condition="trace_memory",
                    trace_text=str(trace_record["trace_text"]),
                    leakage_scan=trace_record["leakage_scan"],
                    robust_adoption=decision,
                    trainable=trainable,
                    trainable_reason=_trainable_reason(trace_record["leakage_scan"], decision, variant),
                    source="generated_minilang_trace",
                )
            )
    return rows


def _build_miniapi_rows(*, seed: int, episodes: int, run_id: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for episode_index in range(episodes):
        episode = make_miniapi_episode(seed + episode_index)
        for variant in MINIAPI_TRACE_VARIANTS:
            trace_record = build_miniapi_trace_record(episode, variant)
            decision = _miniapi_robust_decision(variant)
            trainable = _is_trainable(trace_record["leakage_scan"], decision, variant)
            rows.append(
                _base_row(
                    run_id=run_id,
                    env="MiniAPI",
                    split="train",
                    trace_variant=variant,
                    episode_id=episode.episode_id,
                    family_id=episode.world.family_id,
                    scaffold_condition="trace_memory",
                    trace_text=str(trace_record["trace_text"]),
                    leakage_scan=trace_record["leakage_scan"],
                    robust_adoption=decision,
                    trainable=trainable,
                    trainable_reason=_trainable_reason(trace_record["leakage_scan"], decision, variant),
                    source="generated_miniapi_trace",
                    verifier={"world": asdict(episode.world)},
                )
            )
    return rows


def _base_row(
    *,
    run_id: str,
    env: str,
    split: str,
    trace_variant: str,
    episode_id: str,
    family_id: str,
    scaffold_condition: str,
    trace_text: str,
    leakage_scan: Dict[str, object],
    robust_adoption: Dict[str, object],
    trainable: bool,
    trainable_reason: str,
    source: str,
    verifier: Dict[str, object] | None = None,
) -> Dict[str, object]:
    row = {
        "run_id": run_id,
        "row_id": f"{run_id}:{env}:{episode_id}:{trace_variant}",
        "base_model": "",
        "env": env,
        "split": split,
        "trace_variant": trace_variant,
        "episode_id": episode_id,
        "family_id": family_id,
        "scaffold_condition": scaffold_condition,
        "skill_calls": [],
        "prompt": [],
        "response": trace_text,
        "answers": [],
        "verifier": verifier or {},
        "usage": {},
        "leakage_scan": leakage_scan,
        "robust_adoption": robust_adoption,
        "trainable": trainable,
        "trainable_reason": trainable_reason,
        "source": source,
    }
    row["row_hash"] = hashlib.sha256(
        json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return row


def _is_trainable(
    leakage_scan: Dict[str, object],
    robust_adoption: Dict[str, object],
    trace_variant: str,
) -> bool:
    return (
        trace_variant in TRAINABLE_VARIANTS
        and bool(leakage_scan.get("passed"))
        and robust_adoption.get("decision") == "promote_candidate"
    )


def _trainable_reason(
    leakage_scan: Dict[str, object],
    robust_adoption: Dict[str, object],
    trace_variant: str,
) -> str:
    if trace_variant in RAW_VARIANTS:
        return "blocked_raw_or_source_specific_control"
    if not leakage_scan.get("passed"):
        return "blocked_leakage_scan_failed"
    if robust_adoption.get("decision") != "promote_candidate":
        return f"blocked_robust_adoption_{robust_adoption.get('decision', 'missing')}"
    if trace_variant not in TRAINABLE_VARIANTS:
        return "blocked_variant_not_training_candidate"
    return "trainable_safe_action_memory"


def _minilang_robust_decision(variant: str) -> Dict[str, object]:
    if variant == "raw":
        return {"decision": "quarantine", "reason": "raw_k_spec_control"}
    if variant in {"artifact_scrubbed_executable"}:
        return {"decision": "reject_or_redundant", "reason": "pending_minilang_transfer_gate"}
    return {"decision": "reject_or_redundant", "reason": "pending_minilang_adoption_link"}


def _miniapi_robust_decision(variant: str) -> Dict[str, object]:
    if variant == "raw":
        return {"decision": "quarantine", "reason": "known_source_specific_leakage"}
    if variant in {"action_stripped", "artifact_scrubbed_action"}:
        return {
            "decision": "promote_candidate",
            "reason": "miniapi_memory_proxy_and_adoption_pass",
        }
    return {"decision": "reject_or_redundant", "reason": "no_positive_action_transfer"}


def _missing_required_fields(row: Dict[str, object]) -> List[str]:
    required = [
        "run_id",
        "row_id",
        "env",
        "split",
        "trace_variant",
        "episode_id",
        "family_id",
        "scaffold_condition",
        "prompt",
        "response",
        "answers",
        "verifier",
        "usage",
        "leakage_scan",
        "robust_adoption",
        "trainable",
        "trainable_reason",
    ]
    return [field for field in required if field not in row]

"""Prepare TB2 run artifacts for harness-only ablations and later SFT export.

This module intentionally lives in the Z controller repo.  HarnessX remains the
runnable substrate; these helpers read Harbor/HarnessJournal artifacts without
importing or copying benchmark data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "tb2_sft_candidate_v0"
TRAIN_SPLIT = "train"
HELDOUT_SPLITS = {"heldout", "test"}
MESSAGE_RECORD_TYPES = {"system", "raw_user", "raw_assistant", "raw_tool", "assistant", "tool"}

_LOCAL_PATH_RE = re.compile(r"/Users/[^\s\"']+")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}", re.IGNORECASE)
_LONG_HEX_RE = re.compile(r"\b[0-9a-f]{32,64}\b", re.IGNORECASE)
_TRIAL_RE = re.compile(r"\b[A-Za-z0-9_.-]+__[A-Za-z0-9]{6,10}\b")
_VERIFIER_RE = re.compile(r"(/verifier/|verifier/test-[A-Za-z0-9_.-]+|test-stdout\.txt|test-stderr\.txt)")
_SOLUTION_ECHO_RE = re.compile(
    r"\b(echo|printf)\s+([\"'])(?P<body>[^\"']{1,500})\2(?P<redir>\s*>\s*/app/solution\.txt)",
    re.IGNORECASE | re.DOTALL,
)
_SOLUTION_HEREDOC_RE = re.compile(
    r"(cat\s*>\s*/app/solution\.txt\s*<<\s*['\"]?EOF['\"]?\s*)(?P<body>.*?)(\s*EOF)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class SanitizationReport:
    flags: set[str] = field(default_factory=set)
    replacements: dict[str, int] = field(default_factory=dict)

    def mark(self, name: str, count: int = 1) -> None:
        if count <= 0:
            return
        self.flags.add(name)
        self.replacements[name] = self.replacements.get(name, 0) + count

    def to_dict(self) -> dict[str, Any]:
        return {
            "flags": sorted(self.flags),
            "replacements": dict(sorted(self.replacements.items())),
            "needs_human_review": bool(self.flags),
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    value = timestamp.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def elapsed_seconds(start: str | None, end: str | None) -> float | None:
    started = parse_iso(start)
    finished = parse_iso(end)
    if not started or not finished:
        return None
    return round((finished - started).total_seconds(), 3)


def reward_from_result(result: dict[str, Any]) -> float | None:
    rewards = ((result.get("verifier_result") or {}).get("rewards") or {})
    reward = rewards.get("reward")
    if reward is None:
        return None
    return float(reward)


def task_short_name(task_name: str | None) -> str:
    if not task_name:
        return ""
    return task_name.split("/")[-1]


def task_fingerprint(result: dict[str, Any]) -> str:
    task_id = result.get("task_id") or {}
    parts = [
        str(result.get("source") or ""),
        str(result.get("task_name") or ""),
        str(task_id.get("ref") or ""),
        str(result.get("task_checksum") or ""),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:20]


def artifact_fingerprint(paths: Iterable[Path]) -> str:
    normalized = "|".join(str(path) for path in sorted(paths))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def resolve_content_ref(record: dict[str, Any], jsonl_path: Path) -> dict[str, Any]:
    message = dict(record.get("message") or {})
    meta = record.get("meta") or {}
    content_ref = meta.get("content_ref")
    if content_ref and isinstance(message.get("content"), str):
        ref_path = jsonl_path.parent / str(content_ref)
        if ref_path.is_file():
            message["content"] = ref_path.read_text(encoding="utf-8", errors="replace")
    return message


def load_oh_run_records(oh_runs_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    if not oh_runs_dir.is_dir():
        return records
    for jsonl_path in sorted(oh_runs_dir.rglob("*.jsonl")):
        if jsonl_path.name.endswith("_trace.jsonl"):
            continue
        for record in iter_jsonl(jsonl_path):
            records.append((jsonl_path, record))
    return sorted(records, key=lambda item: (item[1].get("timestamp") or "", item[1].get("step") or -1))


def load_trace_records(oh_runs_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not oh_runs_dir.is_dir():
        return records
    for jsonl_path in sorted(oh_runs_dir.rglob("*_trace.jsonl")):
        records.extend(iter_jsonl(jsonl_path))
    return records


def summarize_trial(trial_result_path: Path) -> dict[str, Any]:
    result = load_json(trial_result_path)
    trial_dir = trial_result_path.parent
    oh_runs_dir = trial_dir / "agent" / "oh_runs"
    session_records = load_oh_run_records(oh_runs_dir)
    trace_records = load_trace_records(oh_runs_dir)

    bash_calls = 0
    assistant_steps: set[int] = set()
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    for _, record in session_records:
        if record.get("type") == "raw_assistant":
            step = record.get("step")
            if isinstance(step, int):
                assistant_steps.add(step)
            for tool_call in (record.get("message") or {}).get("tool_calls") or []:
                if tool_call.get("name") == "Bash":
                    bash_calls += 1
            record_usage = ((record.get("meta") or {}).get("usage") or {})
            for key in usage:
                usage[key] += int(record_usage.get(key) or 0)

    processors: dict[str, int] = {}
    synthetic_blocks = 0
    for record in trace_records:
        if record.get("event_type") == "processor_trigger":
            processor = str(record.get("processor") or "unknown")
            processors[processor] = processors.get(processor, 0) + 1
        if record.get("event_type") == "tool_call" and record.get("approved") is False:
            synthetic_blocks += 1

    return {
        "trial_name": result.get("trial_name") or trial_dir.name,
        "task_name": result.get("task_name"),
        "task_short_name": task_short_name(result.get("task_name")),
        "source": result.get("source"),
        "task_ref": (result.get("task_id") or {}).get("ref"),
        "task_checksum": result.get("task_checksum"),
        "reward": reward_from_result(result),
        "exception_info": result.get("exception_info"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "runtime_seconds": elapsed_seconds(result.get("started_at"), result.get("finished_at")),
        "agent_execution_seconds": elapsed_seconds(
            (result.get("agent_execution") or {}).get("started_at"),
            (result.get("agent_execution") or {}).get("finished_at"),
        ),
        "n_input_tokens": (result.get("agent_result") or {}).get("n_input_tokens"),
        "n_output_tokens": (result.get("agent_result") or {}).get("n_output_tokens"),
        "observed_assistant_steps": len(assistant_steps),
        "observed_bash_tool_calls": bash_calls,
        "raw_usage_from_oh_runs": usage,
        "processor_triggers": processors,
        "synthetic_tool_blocks": synthetic_blocks,
        "paths": {
            "trial_result": str(trial_result_path),
            "trial_dir": str(trial_dir),
            "oh_runs": str(oh_runs_dir),
        },
    }


def summarize_job(job_root: Path) -> dict[str, Any]:
    result_path = job_root / "result.json"
    job_result = load_json(result_path) if result_path.is_file() else {}
    trials = [summarize_trial(path) for path in sorted(job_root.glob("*/result.json"))]
    return {
        "job_name": job_root.name,
        "artifact_root": str(job_root),
        "job_started_at": job_result.get("started_at"),
        "job_finished_at": job_result.get("finished_at"),
        "job_stats": job_result.get("stats"),
        "trials": trials,
    }


def collect_heldout_tasks(split_manifest: dict[str, Any]) -> set[str]:
    heldout = split_manifest.get("splits", {}).get("heldout", {}).get("tasks", [])
    names: set[str] = set()
    for item in heldout:
        if isinstance(item, dict):
            name = item.get("qualified_name") or item.get("name")
        else:
            name = str(item)
        if name:
            names.add(name)
            names.add(task_short_name(name))
            names.add(f"terminal-bench/{task_short_name(name)}")
    return names


def sanitize_text(text: str, task_aliases: Iterable[str], trial_aliases: Iterable[str], report: SanitizationReport) -> str:
    sanitized = text

    for alias in sorted({alias for alias in task_aliases if alias}, key=len, reverse=True):
        sanitized, count = re.subn(re.escape(alias), "<TB2_TASK>", sanitized)
        report.mark("task_id_redacted", count)

    for alias in sorted({alias for alias in trial_aliases if alias}, key=len, reverse=True):
        sanitized, count = re.subn(re.escape(alias), "<TB2_TRIAL>", sanitized)
        report.mark("trial_id_redacted", count)

    sanitized, count = _TRIAL_RE.subn("<TB2_TRIAL>", sanitized)
    report.mark("trial_id_redacted", count)

    sanitized, count = _LOCAL_PATH_RE.subn("<LOCAL_PATH>", sanitized)
    report.mark("local_path_redacted", count)

    sanitized, count = _SHA256_RE.subn("<SHA256>", sanitized)
    report.mark("hash_redacted", count)

    sanitized, count = _LONG_HEX_RE.subn("<HASH>", sanitized)
    report.mark("hash_redacted", count)

    sanitized, count = _VERIFIER_RE.subn("<VERIFIER_ARTIFACT>", sanitized)
    report.mark("verifier_internal_redacted", count)

    def redact_solution_echo(match: re.Match[str]) -> str:
        return f"{match.group(1)} '<CANDIDATE_OUTPUT>'{match.group('redir')}"

    sanitized, count = _SOLUTION_ECHO_RE.subn(redact_solution_echo, sanitized)
    report.mark("solution_literal_redacted", count)

    sanitized, count = _SOLUTION_HEREDOC_RE.subn(r"\\1<CANDIDATE_OUTPUT>\\3", sanitized)
    report.mark("solution_literal_redacted", count)

    if "/app/solution.txt" in sanitized:
        report.mark("solution_path_present")

    return sanitized


def sanitize_obj(value: Any, task_aliases: Iterable[str], trial_aliases: Iterable[str], report: SanitizationReport) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, task_aliases, trial_aliases, report)
    if isinstance(value, list):
        return [sanitize_obj(item, task_aliases, trial_aliases, report) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_obj(item, task_aliases, trial_aliases, report) for key, item in value.items()}
    return value


def build_messages(oh_runs_dir: Path, task_aliases: Iterable[str], trial_aliases: Iterable[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], SanitizationReport]:
    messages: list[dict[str, Any]] = []
    tool_definitions: list[dict[str, Any]] = []
    report = SanitizationReport()
    saw_system = False

    for jsonl_path, record in load_oh_run_records(oh_runs_dir):
        record_type = record.get("type")
        if record_type == "tools" and not tool_definitions:
            content = ((record.get("message") or {}).get("content") or [])
            tool_definitions = sanitize_obj(content, task_aliases, trial_aliases, report)
            continue

        if record_type not in MESSAGE_RECORD_TYPES:
            continue

        if record_type == "assistant" and (record.get("message") or {}).get("content") == "user actively interrupted execution":
            report.mark("interrupted_record_dropped")
            continue

        if record_type == "system":
            if saw_system:
                continue
            saw_system = True

        message = resolve_content_ref(record, jsonl_path)
        if not message:
            continue
        messages.append(sanitize_obj(message, task_aliases, trial_aliases, report))

    return messages, tool_definitions, report


def should_export_entry(entry: dict[str, Any], result: dict[str, Any], heldout_tasks: set[str]) -> tuple[bool, str]:
    split = str(entry.get("split") or "")
    task_name = str(result.get("task_name") or entry.get("task_name") or "")
    aliases = {task_name, task_short_name(task_name)}

    if split in HELDOUT_SPLITS or aliases & heldout_tasks:
        return False, "heldout_or_test_filtered"
    if split != TRAIN_SPLIT:
        return False, "not_train_split"
    if not entry.get("accepted_for_training"):
        return False, "not_accepted_for_training"
    if entry.get("status") != "completed":
        return False, "run_not_completed"
    if reward_from_result(result) != 1.0:
        return False, "reward_not_one"
    return True, "accepted"


def iter_sft_candidates(ledger: dict[str, Any], split_manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    heldout_tasks = collect_heldout_tasks(split_manifest)
    candidates: list[dict[str, Any]] = []
    stats: dict[str, int] = {}

    for entry in ledger.get("entries", []):
        trial_result = Path(str(entry.get("trial_result") or ""))
        if not trial_result.is_file():
            reason = "missing_trial_result"
            stats[reason] = stats.get(reason, 0) + 1
            continue

        result = load_json(trial_result)
        allowed, reason = should_export_entry(entry, result, heldout_tasks)
        stats[reason] = stats.get(reason, 0) + 1
        if not allowed:
            continue

        task_name = str(result.get("task_name") or entry.get("task_name") or "")
        trial_name = str(result.get("trial_name") or entry.get("trial_name") or trial_result.parent.name)
        task_aliases = {task_name, task_short_name(task_name)}
        trial_aliases = {trial_name, trial_result.parent.name}
        oh_runs_dir = trial_result.parent / "agent" / "oh_runs"
        messages, tool_definitions, report = build_messages(oh_runs_dir, task_aliases, trial_aliases)
        if not messages:
            stats["missing_messages"] = stats.get("missing_messages", 0) + 1
            continue

        candidate = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "tb2_sft_candidate",
            "source": {
                "benchmark": "Terminal-Bench",
                "benchmark_version": "2.1",
                "dataset": result.get("source"),
                "task_fingerprint": task_fingerprint(result),
                "artifact_fingerprint": artifact_fingerprint([trial_result, oh_runs_dir]),
                "harness_variant": entry.get("harness_variant"),
                "model": ((result.get("config") or {}).get("agent") or {}).get("model_name"),
            },
            "messages": messages,
            "tool_definitions": tool_definitions,
            "reward": reward_from_result(result),
            "failure_taxonomy": entry.get("failure_taxonomy") or [],
            "provenance": {
                "run_ledger_id": ledger.get("ledger_id"),
                "entry_id": entry.get("entry_id"),
                "split": entry.get("split"),
            },
            "sanitization": report.to_dict(),
        }
        candidates.append(candidate)

    return candidates, stats


def export_sft_candidates(ledger_path: Path, split_manifest_path: Path, output_path: Path) -> dict[str, Any]:
    ledger = load_json(ledger_path)
    split_manifest = load_json(split_manifest_path)
    candidates, stats = iter_sft_candidates(ledger, split_manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate, sort_keys=True) + "\n")

    manifest = {
        "schema_version": "tb2_sft_export_manifest_v0",
        "ledger_path": str(ledger_path),
        "split_manifest_path": str(split_manifest_path),
        "output_path": str(output_path),
        "n_candidates": len(candidates),
        "filter_stats": dict(sorted(stats.items())),
        "policy": {
            "requires_split": TRAIN_SPLIT,
            "requires_accepted_for_training": True,
            "requires_reward": 1.0,
            "filters_heldout_and_test": True,
            "scrubs_task_and_trial_ids": True,
            "scrubs_verifier_artifacts": True,
            "scrubs_literal_solution_writes": True,
        },
    }
    write_json(output_path.with_suffix(output_path.suffix + ".manifest.json"), manifest)
    return manifest


def summarize_command(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize a TB2 Harbor job artifact root.")
    parser.add_argument("job_root", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    summary = summarize_job(args.job_root)
    if args.output:
        write_json(args.output, summary)
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def export_command(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export accepted TB2 SFT candidate records from a run ledger.")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    manifest = export_sft_candidates(args.ledger, args.split_manifest, args.output)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0

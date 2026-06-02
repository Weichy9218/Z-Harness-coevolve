"""Tests for TB2 pre-training preparation and sanitizer policy."""

from __future__ import annotations

import json
from pathlib import Path

from zharness.tb2.pretrain_prep import (
    SanitizationReport,
    export_sft_candidates,
    sanitize_text,
    summarize_trial,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _make_trial(tmp_path: Path, *, task_name: str = "terminal-bench/train-task", reward: float = 1.0) -> Path:
    trial = tmp_path / "job" / "train-task__ABC1234"
    result = {
        "task_name": task_name,
        "trial_name": "train-task__ABC1234",
        "source": "terminal-bench/terminal-bench-2-1",
        "task_id": {"ref": "sha256:" + "a" * 64},
        "task_checksum": "b" * 64,
        "config": {"agent": {"model_name": "deepseek-v3.2"}},
        "agent_result": {"n_input_tokens": 10, "n_output_tokens": 2},
        "verifier_result": {"rewards": {"reward": reward}},
        "started_at": "2026-06-02T00:00:00Z",
        "finished_at": "2026-06-02T00:01:00Z",
        "agent_execution": {
            "started_at": "2026-06-02T00:00:10Z",
            "finished_at": "2026-06-02T00:00:50Z",
        },
    }
    _write_json(trial / "result.json", result)

    session_dir = trial / "agent" / "oh_runs" / "session-1"
    (session_dir / "tool_results").mkdir(parents=True)
    (session_dir / "tool_results" / "tool-1.txt").write_text(
        "/Users/weichy/code/HarnessX/.benchmarks/tb2/job/train-task__ABC1234/verifier/test-stdout.txt\n",
        encoding="utf-8",
    )
    _write_jsonl(
        session_dir / "run-1.jsonl",
        [
            {
                "type": "tools",
                "step": 0,
                "timestamp": "2026-06-02T00:00:00Z",
                "message": {"role": "tools", "content": [{"name": "Bash"}]},
            },
            {
                "type": "system",
                "step": 0,
                "timestamp": "2026-06-02T00:00:00Z",
                "message": {"role": "system", "content": "Solve terminal-bench/train-task."},
            },
            {
                "type": "raw_user",
                "step": 0,
                "timestamp": "2026-06-02T00:00:01Z",
                "message": {"role": "user", "content": "Task train-task__ABC1234 in /Users/weichy/code/HarnessX."},
            },
            {
                "type": "raw_assistant",
                "step": 1,
                "timestamp": "2026-06-02T00:00:02Z",
                "message": {
                    "role": "assistant",
                    "content": "I will write the answer.",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "name": "Bash",
                            "input": {"command": "echo 'secret-word' > /app/solution.txt"},
                        }
                    ],
                },
                "meta": {"usage": {"input_tokens": 7, "output_tokens": 3}},
            },
            {
                "type": "raw_tool",
                "step": 1,
                "timestamp": "2026-06-02T00:00:03Z",
                "message": {"role": "tool", "content": "", "tool_call_id": "call-1", "name": "Bash"},
                "meta": {"content_ref": "tool_results/tool-1.txt"},
            },
        ],
    )
    _write_jsonl(
        session_dir / "run-1_trace.jsonl",
        [
            {"event_type": "processor_trigger", "processor": "AptInstallRecoveryProcessor"},
            {"event_type": "tool_call", "approved": False},
        ],
    )
    return trial / "result.json"


def test_sanitize_text_redacts_task_trial_paths_hashes_and_solution_literal() -> None:
    report = SanitizationReport()
    text = (
        "terminal-bench/crack-7z-hash crack-7z-hash__2FXsYpf "
        "/Users/weichy/code/HarnessX/.benchmarks/x verifier/test-stdout.txt "
        "sha256:" + "a" * 64 + " echo 'secret-word' > /app/solution.txt"
    )

    sanitized = sanitize_text(
        text,
        task_aliases=["terminal-bench/crack-7z-hash", "crack-7z-hash"],
        trial_aliases=["crack-7z-hash__2FXsYpf"],
        report=report,
    )

    assert "crack-7z-hash" not in sanitized
    assert "secret-word" not in sanitized
    assert "/Users/weichy" not in sanitized
    assert "test-stdout.txt" not in sanitized
    assert "<CANDIDATE_OUTPUT>" in sanitized
    assert report.replacements["task_id_redacted"] >= 1
    assert "solution_literal_redacted" in report.flags


def test_summarize_trial_counts_tools_and_processor_signals(tmp_path: Path) -> None:
    trial_result = _make_trial(tmp_path)

    summary = summarize_trial(trial_result)

    assert summary["reward"] == 1.0
    assert summary["observed_bash_tool_calls"] == 1
    assert summary["processor_triggers"]["AptInstallRecoveryProcessor"] == 1
    assert summary["synthetic_tool_blocks"] == 1


def test_export_requires_train_split_and_acceptance(tmp_path: Path) -> None:
    trial_result = _make_trial(tmp_path)
    split_manifest = {
        "splits": {
            "heldout": {
                "tasks": ["terminal-bench/heldout-task"],
            }
        }
    }
    ledger = {
        "ledger_id": "test-ledger",
        "entries": [
            {
                "entry_id": "dev-entry",
                "split": "dev_tuning",
                "status": "completed",
                "accepted_for_training": True,
                "trial_result": str(trial_result),
            }
        ],
    }
    ledger_path = tmp_path / "ledger.json"
    split_path = tmp_path / "split.json"
    output_path = tmp_path / "out.jsonl"
    _write_json(ledger_path, ledger)
    _write_json(split_path, split_manifest)

    manifest = export_sft_candidates(ledger_path, split_path, output_path)

    assert manifest["n_candidates"] == 0
    assert manifest["filter_stats"]["not_train_split"] == 1
    assert output_path.read_text(encoding="utf-8") == ""


def test_export_outputs_sanitized_train_candidate(tmp_path: Path) -> None:
    trial_result = _make_trial(tmp_path)
    split_manifest = {"splits": {"heldout": {"tasks": []}}}
    ledger = {
        "ledger_id": "test-ledger",
        "entries": [
            {
                "entry_id": "train-entry",
                "harness_variant": "H2",
                "split": "train",
                "status": "completed",
                "accepted_for_training": True,
                "trial_result": str(trial_result),
                "failure_taxonomy": ["none"],
            }
        ],
    }
    ledger_path = tmp_path / "ledger.json"
    split_path = tmp_path / "split.json"
    output_path = tmp_path / "out.jsonl"
    _write_json(ledger_path, ledger)
    _write_json(split_path, split_manifest)

    manifest = export_sft_candidates(ledger_path, split_path, output_path)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert manifest["n_candidates"] == 1
    assert rows[0]["schema_version"] == "tb2_sft_candidate_v0"
    assert rows[0]["reward"] == 1.0
    rendered = json.dumps(rows[0])
    assert "train-task__ABC1234" not in rendered
    assert "terminal-bench/train-task" not in rendered
    assert "secret-word" not in rendered
    assert "/Users/weichy" not in rendered
    assert rows[0]["sanitization"]["needs_human_review"] is True


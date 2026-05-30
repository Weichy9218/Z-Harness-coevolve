"""Generate raw, stripped, and scrubbed MiniLang trace-memory datasets."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

from zharness.envs.minilang.generator import all_expected_answers, make_episode
from zharness.envs.minilang.verifier import verify_answers
from zharness.eval.minilang_splits import parse_csv
from zharness.eval.trace_memory import TRACE_VARIANTS, build_trace_record


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    variants = parse_csv(args.variants, TRACE_VARIANTS)
    output_dir = _make_output_dir(args.output_dir)

    records: List[Dict[str, object]] = []
    for episode_index in range(args.episodes):
        seed = args.seed + episode_index
        episode = make_episode(
            seed,
            support_budget=args.support_budget,
            parse_tasks=args.parse_tasks,
            generate_tasks=args.generate_tasks,
            difficulty=args.difficulty,
        )
        oracle_result = verify_answers(episode.world, episode.tasks, all_expected_answers(episode.world, episode.tasks))
        if oracle_result.accuracy != 1.0:
            raise RuntimeError(f"oracle verification failed for {episode.episode_id}")

        for variant in variants:
            record = build_trace_record(episode, variant)
            record["seed"] = seed
            record["difficulty"] = args.difficulty
            records.append(record)
            _append_jsonl(output_dir / "traces.jsonl", record)
            scan = record["leakage_scan"]
            print(
                f"{episode.episode_id} {variant:<18s} "
                f"leakage_pass={scan['passed']} violations={scan['num_violations']}"
            )

    summary = _summarize(records)
    manifest = {
        "config": vars(args),
        "variants": variants,
        "summary": summary,
        "num_records": len(records),
        "split_contract": {
            "raw": "contains source K_spec and must fail leakage scan",
            "stripped": "strategy trace without source surface artifacts",
            "artifact_scrubbed": "strict reusable policy trace without source artifacts",
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote trace dataset to {output_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return manifest


def _summarize(records: List[Dict[str, object]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for record in records:
        grouped.setdefault(str(record["trace_variant"]), []).append(record)

    summary: Dict[str, Dict[str, float]] = {}
    for variant, variant_records in grouped.items():
        scans = [record["leakage_scan"] for record in variant_records]
        summary[variant] = {
            "n": len(variant_records),
            "leakage_pass_rate": mean(1.0 if scan["passed"] else 0.0 for scan in scans),
            "avg_violations": mean(float(scan["num_violations"]) for scan in scans),
            "avg_trace_chars": mean(float(record["trace_chars"]) for record in variant_records),
        }
    return summary


def _make_output_dir(raw_output_dir: Optional[str]) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "minilang_trace_dataset" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--support-budget", type=int, default=8)
    parser.add_argument("--parse-tasks", type=int, default=4)
    parser.add_argument("--generate-tasks", type=int, default=4)
    parser.add_argument("--difficulty", choices=("basic", "hard"), default="hard")
    parser.add_argument("--variants", default=",".join(TRACE_VARIANTS))
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_experiment(args)


if __name__ == "__main__":
    main()

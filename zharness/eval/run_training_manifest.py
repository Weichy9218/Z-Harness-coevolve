"""Export and validate the shared no-GPU training manifest."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from zharness.eval.miniapi_splits import parse_csv
from zharness.eval.training_manifest import (
    build_manifest_rows,
    manifest_fingerprint,
    validate_manifest_rows,
    write_manifest_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ENVS = ("minilang", "miniapi")


def run_export(args: argparse.Namespace) -> dict:
    envs = parse_csv(args.envs, ENVS)
    output_dir = _make_output_dir(args.output_dir)
    rows = build_manifest_rows(
        envs=envs,
        seed=args.seed,
        episodes=args.episodes,
        run_id=args.run_id,
    )
    errors = validate_manifest_rows(rows)
    if errors:
        (output_dir / "manifest_errors.json").write_text(
            json.dumps(errors, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        raise SystemExit(f"manifest validation failed with {len(errors)} errors; see {output_dir}")

    manifest_path = output_dir / "manifest.jsonl"
    write_manifest_jsonl(manifest_path, rows)
    trainable_rows = [row for row in rows if row["trainable"]]
    summary = {
        "config": vars(args),
        "num_rows": len(rows),
        "num_trainable_rows": len(trainable_rows),
        "fingerprint": manifest_fingerprint(rows),
        "trainable_by_env": _count_by(trainable_rows, "env"),
        "rows_by_env": _count_by(rows, "env"),
        "rows_by_variant": _count_by(rows, "trace_variant"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote validated manifest to {manifest_path}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def _count_by(rows: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field, ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _make_output_dir(raw_output_dir: str | None) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "training_manifest" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--envs", default="minilang,miniapi")
    parser.add_argument("--run-id", default="nogpu-manifest-v0")
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    run_export(build_parser().parse_args())


if __name__ == "__main__":
    main()

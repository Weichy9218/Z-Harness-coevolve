# No-GPU Training Manifest Gate

This note records the first shared manifest exporter and validator. Its purpose
is not to train yet; it is to make the next training step fail closed unless a
row is both leakage-safe and robustly adopted.

## Code Change

Added:

- `zharness/eval/training_manifest.py`
- `zharness/eval/run_training_manifest.py`
- `tests/test_training_manifest.py`

The manifest rows follow the contract in `docs/TRAINING_PLAN.md` and add:

- `robust_adoption`
- `trainable`
- `trainable_reason`
- `row_hash`
- `source`

Validator rule:

```text
trainable=true requires:
  leakage_scan.passed == true
  robust_adoption.decision == "promote_candidate"
  trace_variant not in {"raw", "raw_action"}
```

Any raw/source-specific or quarantined row can remain in the manifest only as a
control row with `trainable=false`.

## Checks

Run:

```bash
.venv/bin/python -m pytest
```

Result:

```text
30 passed
```

## Manifest Smoke

Run:

```bash
.venv/bin/python -m zharness.eval.run_training_manifest --episodes 2 --seed 31
```

Artifacts:

- `runs/training_manifest/20260601-001752/manifest.jsonl`
- `runs/training_manifest/20260601-001752/summary.json`

Summary:

| field | value |
| --- | ---: |
| rows | 18 |
| trainable rows | 4 |
| MiniLangHard rows | 10 |
| MiniAPI rows | 8 |
| trainable MiniAPI rows | 4 |

Variant counts:

| variant | rows |
| --- | ---: |
| `raw` | 4 |
| `stripped` | 2 |
| `executable_stripped` | 2 |
| `artifact_scrubbed` | 4 |
| `artifact_scrubbed_executable` | 2 |
| `action_stripped` | 2 |
| `artifact_scrubbed_action` | 2 |

Fingerprint:

```text
7f144b29c21d307679bbff756dbcff5b7749dab318d0c52f9f26f8c431f171b3
```

## Interpretation

This is the current GPU boundary.

- MiniAPI safe action memories can enter a trainable manifest because they pass
  leakage scan and robust adoption.
- MiniAPI raw traces are retained only as leakage controls.
- MiniLang rows are currently retained as non-trainable until a later run
  proves a robust trainable action-memory row for MiniLang.
- Any future SFT / veRL script should consume this manifest or a stricter one,
  not ad hoc JSONL records.

Next work that materially changes weights requires GPU or a hosted training
runtime. Local no-GPU work can still improve reporting and reproduce HarnessX
harness-only smoke, but the weight-update boundary is now explicit and
machine-checkable.

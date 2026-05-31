# Day 10 Follow-up: MiniAPI Memory Proxy and Adoption

This note records the no-GPU MiniAPI memory-proxy and robust-adoption smokes.
It extends `DAY10_MINIAPI_SMOKE.md` from a headroom/counterfactual simulator
check into the first MiniAPI experience-allocation check.

## Code Change

Added MiniAPI-specific evaluation utilities:

- `zharness/eval/miniapi_trace_memory.py`
- `zharness/eval/miniapi_splits.py`
- `zharness/eval/run_miniapi_memory_proxy.py`
- `zharness/eval/run_miniapi_adoption.py`
- `tests/test_miniapi_env.py`

The MiniAPI memory variants are:

| variant | meaning |
| --- | --- |
| `none` | naive target plan without memory |
| `raw` | previous episode's concrete source profile and successful plan |
| `action_stripped` | abstract action protocol using target-world bounded probes |
| `artifact_scrubbed` | generic non-action policy with source identifiers removed |
| `artifact_scrubbed_action` | action protocol plus explicit quarantine/adoption criteria |

The leakage scanner rejects source family ids, order ids, credentials, coupon
codes, exact source rulebooks, and hidden-profile markers.

## Checks

Run:

```bash
.venv/bin/python -m pytest
```

Result:

```text
28 passed
```

## Memory Proxy Run

Run:

```bash
.venv/bin/python -m zharness.eval.run_miniapi_memory_proxy --episodes 4 --seed 31
```

Artifacts:

- `runs/miniapi_memory_proxy/20260601-001213/records.jsonl`
- `runs/miniapi_memory_proxy/20260601-001213/summary.json`

### Result

| transform | variant | success | completion | leakage pass | query | verifier |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| same_world | `none` | 0.000 | 0.000 | 1.000 | 0 | 0 |
| same_world | `raw` | 1.000 | 1.000 | 0.000 | 0 | 0 |
| same_world | `action_stripped` | 1.000 | 1.000 | 1.000 | 25 | 25 |
| same_world | `artifact_scrubbed` | 0.000 | 0.546 | 1.000 | 0 | 0 |
| same_world | `artifact_scrubbed_action` | 1.000 | 1.000 | 1.000 | 25 | 25 |
| counterfactual_world | `none` | 0.000 | 0.000 | 1.000 | 0 | 0 |
| counterfactual_world | `raw` | 0.000 | 0.433 | 0.000 | 0 | 0 |
| counterfactual_world | `action_stripped` | 1.000 | 1.000 | 1.000 | 43 | 43 |
| counterfactual_world | `artifact_scrubbed` | 0.000 | 0.475 | 1.000 | 0 | 0 |
| counterfactual_world | `artifact_scrubbed_action` | 1.000 | 1.000 | 1.000 | 43 | 43 |
| heldout_world | `none` | 0.000 | 0.000 | 1.000 | 0 | 0 |
| heldout_world | `raw` | 0.500 | 0.750 | 0.000 | 0 | 0 |
| heldout_world | `action_stripped` | 1.000 | 1.000 | 1.000 | 20 | 20 |
| heldout_world | `artifact_scrubbed` | 0.000 | 0.594 | 1.000 | 0 | 0 |
| heldout_world | `artifact_scrubbed_action` | 1.000 | 1.000 | 1.000 | 20 | 20 |

## Adoption Run

Run:

```bash
.venv/bin/python -m zharness.eval.run_miniapi_adoption --episodes 4 --seed 31
```

Artifacts:

- `runs/miniapi_adoption/20260601-001213/records.jsonl`
- `runs/miniapi_adoption/20260601-001213/summary.json`

### Robust Decisions

| skill | seen delta | counterfactual delta | heldout delta | decision | reason |
| --- | ---: | ---: | ---: | --- | --- |
| `kg_auth_first` | 1.000 | 1.000 | 1.000 | promote_candidate | nonnegative counterfactual and heldout delta |
| `kg_probe_hidden_profile` | 0.000 | 1.000 | 0.500 | promote_candidate | nonnegative counterfactual and heldout delta |
| `kspec_source_profile` | 0.000 | -1.000 | -0.500 | quarantine | known source-specific leakage |
| `trap_skip_receipt` | -0.500 | -0.500 | -0.250 | quarantine | counterfactual or heldout negative |

Naive adoption is misleading in this smoke: `kspec_source_profile` has the
highest adoption score (`0.5`) because it is called in every transform, but the
removal deltas prove negative transfer. This is the MiniAPI analogue of the
Day 6 K_spec adoption trap.

## Interpretation

This is still symbolic and no-GPU. It does not claim a trained model has learned
the action protocol. It does show that the MiniAPI environment can express the
same core boundary as MiniLang:

- raw source experience can help same-world score but fails leakage scan;
- raw source profile does not robustly transfer to counterfactual worlds;
- action-stripped memories transfer when they are re-grounded through current
  episode probes;
- robust adoption promotes generic workflow skills and quarantines
  source-specific profiles.

## Remaining Gate Before GPU

Before creating SFT / veRL manifests, one more no-GPU step is needed:

1. export a single manifest schema shared by MiniLang and MiniAPI;
2. mark every row as `trainable=false` unless leakage scan passes and robust
   adoption is `promote_candidate`;
3. add a validation command that fails if raw/source-specific records are routed
   to trainable manifests.

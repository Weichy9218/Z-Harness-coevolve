# Day 10 Smoke: MiniAPI / ToolWorld

This note records the first no-GPU MiniAPI environment and smoke run. The goal
is to move beyond MiniLang into a stateful tool/API setting while keeping the
same scientific contract: hidden current-episode facts can help the harness,
but source-specific facts must not be promoted into weights.

## Code Change

Added a deterministic MiniAPI simulator:

- `zharness/envs/miniapi/simulator.py`
- `zharness/eval/run_miniapi.py`
- `tests/test_miniapi_env.py`

The simulator models a small order-fulfillment API workflow with hidden
constraints:

- coupon must be applied before or after inventory reservation depending on
  the current world;
- risk check may be required before payment;
- receipt may be required before shipping;
- carrier choice depends on priority and hidden world profile;
- all write tools require authentication;
- final success is verified by state, not by text matching.

The simulator stays under the Day 10 size target: `simulator.py` is 413 lines.

## Conditions

| condition | meaning |
| --- | --- |
| `no_scaffold` | naive tool plan without hidden constraints |
| `k_spec` | target-world rulebook / oracle plan |
| `k_gen_exec` | bounded diagnostic probes on non-target probe orders, then execute inferred plan |
| `source_raw` | plan generated from a counterfactual source world and executed on target |
| `target_scaffold` | alias of target-world diagnostic probing, matching the scaffold-distillation framing |

`k_gen_exec` records:

- `query_calls`
- `verifier_calls`
- `direct_target_query_violations`
- structured probe trace with candidate profile, probe id, success, and errors.

## Deterministic Checks

Run:

```bash
.venv/bin/python -m pytest
```

Result:

```text
25 passed
```

## Smoke Run

Run:

```bash
.venv/bin/python -m zharness.eval.run_miniapi --episodes 4 --seed 31
```

Artifacts:

- `runs/miniapi/20260601-000429/records.jsonl`
- `runs/miniapi/20260601-000429/summary.json`

## Result

| condition | success | completion | robustness | tool use | forbidden action rate | query | verifier | target-query violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_scaffold` | 0.000 | 0.000 | 0.000 | 0.722 | 1.000 | 0 | 0 | 0 |
| `k_spec` | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0 | 0 | 0 |
| `k_gen_exec` | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 25 | 25 | 0 |
| `source_raw` | 0.000 | 0.433 | 0.433 | 0.866 | 0.000 | 0 | 0 | 0 |
| `target_scaffold` | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 25 | 25 | 0 |

## Interpretation

This is a protocol smoke, not a paper result.

Positive signal:

- `k_gen_exec` and `target_scaffold` recover the hidden API workflow with
  bounded diagnostic probes.
- `source_raw` fails on counterfactual target worlds even though the plan is
  well-formed, which is the desired MiniAPI analogue of K_spec leakage.
- direct target query violations are zero: probes use separate probe orders,
  not the exact target order id.

Current limitation:

- the executor is still symbolic; no LLM has been asked to infer the workflow
  from probe traces.
- the probe search is exhaustive over a small hidden-profile space, so it is a
  clean scaffold mechanism rather than a realistic policy.
- memory proxy and robust adoption have not yet been ported from MiniLang to
  MiniAPI.

## Next Gate

Before any GPU training:

1. Add MiniAPI counterfactual/adoption sweeps, using removal delta rather than
   naive call-rate reward.
2. Export MiniAPI action traces in raw / action-stripped /
   artifact-scrubbed variants.
3. Run memory proxy on MiniAPI and require heldout/counterfactual transfer
   before producing SFT / veRL manifests.

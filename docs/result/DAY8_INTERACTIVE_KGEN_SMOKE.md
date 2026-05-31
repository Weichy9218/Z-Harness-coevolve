# Day 8 Smoke: Interactive K_gen

This is a factual note for the first `k_gen_interactive` implementation smoke.
The goal was to decide whether the interactive protocol is concise and effective
enough to justify a larger dataset run.

## Code Change

Added a bounded interactive runner for MiniLang headroom:

- `zharness/eval/interactive_kgen.py`
- `zharness/eval/run_headroom.py`
- `zharness/agents/prompts.py`
- `tests/test_minilang_env.py`

The new condition is:

```text
k_gen_interactive
```

It executes one fixed action loop:

```text
k_gen_exec draft -> verifier feedback -> one-step repair -> final answers
```

The runner records:

- `action_trace`
- `query_calls`
- `verifier_calls`
- `repair_count`
- `final_attempts`
- `direct_target_query_violations`

The implementation rejects exact generation-target queries and returns coarse
field-level verifier labels rather than corrected answers.

After the first five-arm smoke, the runner was tightened with:

- a compact single-field pair evidence table for the draft/final prompts;
- a no-regression merge that preserves draft answers marked `correct=true` by
  verifier feedback.
- a slot-table state with action/object/color/count/agreement/negation/order
  fields;
- a deterministic minimal-pair coverage gate, replacing the unstable pre-query
  model planner.
- final lean repair: remove slot-table prompting; use the direct `k_gen_exec`
  draft, one coarse verifier pass, and one compact repair prompt.

## Deterministic Checks

Run:

```bash
.venv/bin/python -m pytest
```

Result:

```text
20 passed
```

## API Smoke Iterations

All API smokes used:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_headroom \
  --episodes 1 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --conditions k_gen_interactive \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none
```

| run | change tested | accuracy | parse | generate | query | verifier | repair | tokens | note |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `runs/day8-interactive-kgen-smoke1` | initial schema | 0.000 | 0.000 | 0.000 | 8 | 1 | 0 | 8635 | model wrote long hypothesis notes; final JSON did not parse answers |
| `runs/day8-interactive-kgen-smoke2` | compact schema, no raw action responses | 0.000 | 0.000 | 0.000 | 1 | 1 | 1 | 3051 | concise, but planner under-used query budget |
| `runs/day8-interactive-kgen-smoke3` | require exactly 8 queries | 0.000 | 0.000 | 0.000 | 8 | 1 | 1 | 3972 | correct action shape, still no task success |
| `runs/day8-interactive-kgen-smoke4` | field-level generation feedback | 0.000 | 0.000 | 0.000 | 8 | 1 | 1 | 4422 | feedback improved diagnostics, not outcome |
| `runs/day8-interactive-kgen-smoke5` | structured morpheme observations | 0.250 | 0.250 | 0.250 | 8 | 1 | 1 | 4787 | first positive signal, but still weak |
| `runs/day8-interactive-kgen-smoke6` | slot table + task-label repair | 0.500 | 0.750 | 0.250 | 8 | 1 | 1 | 6173 | improved but unstable |
| `runs/day8-interactive-kgen-smoke7` | minimal-pair coverage gate | 0.250 | 0.000 | 0.500 | 8 | 1 | 1 | 7373 | coverage helped generation, hurt parse |
| `runs/day8-interactive-kgen-smoke8` | phrase-role slot table | 0.375 | 0.250 | 0.500 | 8 | 1 | 1 | 7653 | clearer state, still too costly |
| `runs/day8-interactive-kgen-smoke9` | remove pre-query model planner | 0.375 | 0.250 | 0.500 | 8 | 1 | 1 | 6412 | lower cost, still below `k_gen_exec` |

## Five-arm Headroom Smoke

Run:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_headroom \
  --episodes 1 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --conditions no_scaffold,k_gen,k_gen_exec,k_gen_interactive,k_spec \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --output-dir runs/day8-interactive-headroom-smoke1
```

Result:

| condition | accuracy | parse | generate | query | verifier | repair | tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_scaffold` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 880 |
| `k_gen` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 1019 |
| `k_gen_exec` | 0.750 | 0.750 | 0.750 | 8 | 0 | 0 | 1424 |
| `k_gen_interactive` | 0.125 | 0.250 | 0.000 | 8 | 1 | 1 | 4936 |
| `k_spec` | 0.875 | 1.000 | 0.750 | 0 | 0 | 0 | 1149 |

## Post-repair Five-arm Smoke

After adding pair evidence and no-regression merge, the same one-episode
five-arm smoke was rerun:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_headroom \
  --episodes 1 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --conditions no_scaffold,k_gen,k_gen_exec,k_gen_interactive,k_spec \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --output-dir runs/day8-interactive-headroom-smoke2
```

Result:

| condition | accuracy | parse | generate | query | verifier | repair | no-regression merge | tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_scaffold` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 0 | 892 |
| `k_gen` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 0 | 1019 |
| `k_gen_exec` | 0.875 | 0.750 | 1.000 | 8 | 0 | 0 | 0 | 1425 |
| `k_gen_interactive` | 0.250 | 0.500 | 0.000 | 8 | 1 | 1 | 0 | 5397 |
| `k_spec` | 0.875 | 1.000 | 0.750 | 0 | 0 | 0 | 0 | 1149 |

## Memory and Adoption Code Readiness

No API memory-proxy or adoption sweep has been rerun yet. The code path was
prepared for the next run:

- `run_memory_proxy` now supports `executable_stripped` and
  `artifact_scrubbed_executable` trace variants in addition to raw/prose
  stripped/artifact-scrubbed traces.
- `run_adoption` now reports `robust_adoption`, separating same-world,
  counterfactual, and heldout removal delta before promotion.
- Mock adoption and memory-proxy runs completed under `/tmp`.

## Slot-table Five-arm Smoke

After the slot-table and deterministic coverage-gate repair, the five-arm smoke
was rerun:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_headroom \
  --episodes 1 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --conditions no_scaffold,k_gen,k_gen_exec,k_gen_interactive,k_spec \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --output-dir runs/day8-interactive-headroom-smoke5
```

Result:

| condition | accuracy | parse | generate | query | verifier | repair | coverage query | slot repair | tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_scaffold` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 0 | 0 | 889 |
| `k_gen` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 0 | 0 | 1019 |
| `k_gen_exec` | 0.875 | 0.750 | 1.000 | 8 | 0 | 0 | 0 | 0 | 1424 |
| `k_gen_interactive` | 0.250 | 0.250 | 0.250 | 8 | 1 | 1 | 8 | 1 | 6427 |
| `k_spec` | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 | 0 | 0 | 1149 |

## Lean Repair Five-arm Smoke

After removing the slot-table prompt and using the direct `k_gen_exec` answer
as the draft, the same one-episode five-arm smoke was rerun:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_headroom \
  --episodes 1 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --conditions no_scaffold,k_gen,k_gen_exec,k_gen_interactive,k_spec \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --output-dir runs/day8-interactive-headroom-smoke6
```

Result:

| condition | accuracy | parse | generate | query | verifier | repair | tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_scaffold` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 893 |
| `k_gen` | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 1019 |
| `k_gen_exec` | 0.875 | 0.750 | 1.000 | 8 | 0 | 0 | 1424 |
| `k_gen_interactive` | 0.875 | 0.750 | 1.000 | 8 | 1 | 1 | 3491 |
| `k_spec` | 0.875 | 1.000 | 0.750 | 0 | 0 | 0 | 1149 |

This smoke showed that the lean repair path preserves `k_gen_exec` quality and
cuts the earlier slot-table cost roughly in half, but it did not yet prove a
mean improvement.

## Lean Repair 8-episode Headroom

The 8-episode hard-mode headroom rerun used:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_headroom \
  --episodes 8 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --conditions no_scaffold,k_gen,k_gen_exec,k_gen_interactive,k_spec \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --output-dir runs/day8-interactive-headroom-8ep-lean
```

Result:

| condition | accuracy | parse | generate | query | verifier | repair | tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_scaffold` | 0.062 | 0.094 | 0.031 | 0 | 0 | 0 | 6946 |
| `k_gen` | 0.062 | 0.094 | 0.031 | 0 | 0 | 0 | 8097 |
| `k_gen_exec` | 0.609 | 0.625 | 0.594 | 64 | 0 | 0 | 11272 |
| `k_gen_interactive` | 0.750 | 0.656 | 0.844 | 64 | 8 | 8 | 27021 |
| `k_spec` | 0.891 | 1.000 | 0.781 | 0 | 0 | 0 | 9122 |

Per-episode deltas vs `k_gen_exec`:

| episode | acc delta | generate delta |
| --- | ---: | ---: |
| `episode-7` | 0.000 | 0.000 |
| `episode-8` | +0.125 | +0.250 |
| `episode-9` | +0.125 | +0.250 |
| `episode-10` | 0.000 | 0.000 |
| `episode-11` | +0.125 | +0.250 |
| `episode-12` | +0.250 | +0.250 |
| `episode-13` | +0.125 | +0.250 |
| `episode-14` | +0.375 | +0.750 |

## Memory Proxy 2-episode Smoke

After the headroom gate passed, a small memory-proxy rerun used:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_memory_proxy \
  --episodes 2 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --transforms renamed_vocab,composition_swap,heldout_family \
  --memory-variants none,raw,stripped,executable_stripped,artifact_scrubbed,artifact_scrubbed_executable \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --output-dir runs/day8-memory-proxy-2ep-exec
```

Result summary:

| transform | best safe variant | best safe acc | raw acc | raw leakage pass |
| --- | --- | ---: | ---: | ---: |
| `renamed_vocab` | `artifact_scrubbed_executable` | 0.125 | 0.000 | 0.000 |
| `composition_swap` | none above baseline | 0.000 | 0.312 | 0.000 |
| `heldout_family` | none above baseline | 0.000 | 0.062 | 0.000 |

Safe variants pass leakage scan, but the current executable memory templates do
not yet transfer reliably. Raw memory is useful only in source-specific ways
and fails the leakage scan.

## Adoption 2-episode Smoke

The robust-adoption rerun used:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_adoption \
  --episodes 2 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --transforms same_world,composition_swap,heldout_family \
  --max-called-skills 2 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --output-dir runs/day8-adoption-2ep-robust
```

The first summary exposed a gate bug: `kspec_source_rulebook` was promoted
because removal delta was positive on same-world and composition-swap. The code
now gives known source-specific leakage skills a hard quarantine prior. The
same records were re-summarized without rerunning API calls.

Corrected robust classification:

| skill | decision | reason | seen delta | counterfactual mean | heldout delta |
| --- | --- | --- | ---: | ---: | ---: |
| `kg_minimal_contrast` | reject_or_redundant | no_positive_removal_delta | 0.000 | -0.062 | 0.000 |
| `kg_generation_audit` | reject_or_redundant | no_positive_removal_delta | 0.000 | -0.062 | 0.000 |
| `kspec_source_rulebook` | quarantine | known_source_specific_leakage | 0.938 | 0.438 | 0.000 |
| `trap_ignore_agreement` | reject_or_redundant | no_positive_removal_delta | 0.000 | -0.062 | -0.062 |
| `redundant_minimal_probe` | reject_or_redundant | no_positive_removal_delta | 0.000 | 0.000 | -0.062 |

## Interpretation

What passed:

1. The code path is executable and records the intended cost/action fields.
2. The final action trace is much more compact after removing raw per-step
   responses from `action_trace`.
3. The protocol enforces bounded queries and rejects direct generation-target
   queries.
4. Structured morpheme observations are better than free-form observations.
5. Pair evidence improved the five-arm smoke from 0.125 to 0.250 accuracy.
6. Slot-table and coverage-gate repairs can improve single-arm generation to
   0.500, but this did not hold in five-arm comparison.
7. The lean repair path beats `k_gen_exec` over 8 hard episodes: 0.750 vs
   0.609 accuracy, with generation improving from 0.594 to 0.844.
8. Robust adoption now quarantines the explicit source rulebook skill even when
   naive removal delta would promote it.

What did not pass:

1. The lean repair path is still more expensive than `k_gen_exec`: 27021 vs
   11272 total tokens over 8 episodes.
2. The main improvement is generation; parse only improves from 0.625 to
   0.656.
3. Memory-proxy and adoption reruns are only 2-episode smokes, not final-scale evidence.
4. Safe memory variants do not yet reproduce the headroom gain; executable
   stripped memory is mostly neutral in the 2-episode proxy.

Decision:

The previous slot-table protocol should not be used. The lean repair protocol
is the current `k_gen_interactive` candidate: it is effective on 8-episode
headroom, but not yet cost-efficient. Training is still blocked because safe
memory variants do not yet transfer reliably.

## Next Repair

Next:

1. improve executable/action-stripped trace generation so memory proxy captures
   the successful lean repair behavior rather than a generic template;
2. rerun memory proxy before training;
3. only consider training/data generation if executable/action-stripped memory
   does not behave like source-specific K_spec under counterfactual and heldout
   splits.

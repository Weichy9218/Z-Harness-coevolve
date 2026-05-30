# Day 4-6 API-only Report: Trace, Proxy, Adoption

This file is the factual report for the no-training Day 4, Day 5, and Day 6
work. The goal was to use API calls and harness artifacts only: no SFT, no LoRA,
no verl, no weight updates.

## Harness Architecture Used

The work stays inside the existing `zharness` shape:

- `zharness/envs/minilang/`: deterministic episode generator, transforms, verifier.
- `zharness/eval/minilang_splits.py`: shared split/transform construction used by leakage, memory proxy, and adoption runners.
- `zharness/eval/trace_memory.py`: raw / stripped / artifact-scrubbed trace builders and leakage scanner.
- `zharness/eval/run_trace_dataset.py`: Day 4 trace dataset runner.
- `zharness/eval/run_memory_proxy.py`: Day 5 API-only in-context memory proxy.
- `zharness/eval/run_adoption.py`: Day 6 frozen skill library, top-k invocation, and removal ablation.
- Every runner writes `records.jsonl` plus `summary.json` or `manifest.json` under `runs/`.

The important discipline is that the report reads from run artifacts. It does
not invent metrics and does not use any training result.

## Day 4: Raw / Stripped / Scrubbed Trace Dataset

Run:

```bash
.venv/bin/python -m zharness.eval.run_trace_dataset \
  --episodes 8 \
  --difficulty hard \
  --support-budget 8 \
  --output-dir runs/day4-trace-dataset-hard-v0
```

Artifacts:

- `runs/day4-trace-dataset-hard-v0/traces.jsonl`
- `runs/day4-trace-dataset-hard-v0/manifest.json`

Trace variants:

- `raw`: contains source rulebook, source examples, source final answers. This
  is the leakage control and should fail the scanner.
- `stripped`: keeps reusable rule-discovery procedure, removes source surface
  artifacts.
- `artifact_scrubbed`: stricter policy-level trace; shorter and explicitly
  says to quarantine prior surface forms, answers, family identifiers, and
  concrete rulebooks.

Result:

| variant | n | leakage pass rate | avg violations | avg chars |
| --- | ---: | ---: | ---: | ---: |
| `raw` | 8 | 0.000 | 31.125 | 2569.125 |
| `stripped` | 8 | 1.000 | 0.000 | 795.000 |
| `artifact_scrubbed` | 8 | 1.000 | 0.000 | 466.000 |

Interpretation:

1. The scrubber is discriminative enough for the next step: it catches raw
   `K_spec` and lets stripped/scrubbed traces through.
2. The scanner is intentionally syntactic. It catches surface atoms, exact
   source commands, family ids, episode ids, and explicit source rulebook
   markers. It does not prove semantic non-leakage.
3. Day 4 gate passes for API-only proxy experiments.

## Day 5: API-only Trace Memory Proxy

Run:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_memory_proxy \
  --episodes 4 \
  --difficulty hard \
  --support-budget 8 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --transforms renamed_vocab,composition_swap,heldout_family \
  --memory-variants none,raw,stripped,artifact_scrubbed \
  --output-dir runs/day5-memory-proxy-hard-deepseek-v0
```

Artifacts:

- `runs/day5-memory-proxy-hard-deepseek-v0/records.jsonl`
- `runs/day5-memory-proxy-hard-deepseek-v0/summary.json`

Result:

| transform | memory | n | accuracy | parse | generate | avg tokens | leakage pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `renamed_vocab` | `none` | 4 | 0.125 | 0.125 | 0.125 | 1086.75 | 1.000 |
| `renamed_vocab` | `raw` | 4 | 0.062 | 0.062 | 0.062 | 1979.00 | 0.000 |
| `renamed_vocab` | `stripped` | 4 | 0.062 | 0.062 | 0.062 | 1209.50 | 1.000 |
| `renamed_vocab` | `artifact_scrubbed` | 4 | 0.062 | 0.062 | 0.062 | 1195.25 | 1.000 |
| `composition_swap` | `none` | 4 | 0.062 | 0.062 | 0.062 | 1057.50 | 1.000 |
| `composition_swap` | `raw` | 4 | 0.438 | 0.875 | 0.000 | 1983.75 | 0.000 |
| `composition_swap` | `stripped` | 4 | 0.062 | 0.062 | 0.062 | 1254.50 | 1.000 |
| `composition_swap` | `artifact_scrubbed` | 4 | 0.094 | 0.125 | 0.062 | 1201.25 | 1.000 |
| `heldout_family` | `none` | 4 | 0.219 | 0.188 | 0.250 | 1094.75 | 1.000 |
| `heldout_family` | `raw` | 4 | 0.000 | 0.000 | 0.000 | 1985.50 | 0.000 |
| `heldout_family` | `stripped` | 4 | 0.344 | 0.438 | 0.250 | 1255.00 | 1.000 |
| `heldout_family` | `artifact_scrubbed` | 4 | 0.344 | 0.312 | 0.375 | 1202.50 | 1.000 |

Interpretation:

1. Raw memory is not safe. It fails the leakage scanner, nearly doubles token
   cost, and collapses on `heldout_family`.
2. `composition_swap` raw memory raises parse to 0.875 but generation remains
   0.000. This is exactly the K_spec failure mode: old lexical semantics help
   semantic decoding, but old structure does not transfer.
3. Stripped and artifact-scrubbed traces are not a strong universal win yet.
   They do not help `renamed_vocab`, barely move `composition_swap`, and help
   only `heldout_family`.
4. The best positive signal is held-out transfer: `none` 0.219 vs
   stripped/scrubbed 0.344. That is small and noisy, but it is in the right
   direction and does not leak.

Decision:

- Day 5 supports using stripped/scrubbed traces as API-only proxy candidates.
- It does not yet justify SFT. The effect is too small and split-dependent.
- Before training, improve the stripped trace into a more executable discovery
  scaffold with explicit query/verifier steps.

## Day 6: Offline Adoption Signal

Run:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_adoption \
  --episodes 3 \
  --difficulty hard \
  --support-budget 8 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --transforms same_world,composition_swap,heldout_family \
  --max-called-skills 2 \
  --output-dir runs/day6-adoption-hard-deepseek-v0
```

Artifacts:

- `runs/day6-adoption-hard-deepseek-v0/records.jsonl`
- `runs/day6-adoption-hard-deepseek-v0/summary.json`

Frozen skill library:

- `kg_minimal_contrast`: useful generic K_gen.
- `kg_generation_audit`: useful generic generation check.
- `kspec_source_rulebook`: source episode K_spec leak.
- `trap_ignore_agreement`: misleading skill.
- `redundant_minimal_probe`: redundant generic skill.

Full-library result:

| transform | n | accuracy | parse | generate | avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `same_world` | 3 | 0.917 | 1.000 | 0.833 | 1451.67 |
| `composition_swap` | 3 | 0.542 | 1.000 | 0.083 | 1483.33 |
| `heldout_family` | 3 | 0.000 | 0.000 | 0.000 | 1505.00 |

Adoption summary from full-library runs:

| skill | call count | call rate | success when called | adoption score |
| --- | ---: | ---: | ---: | ---: |
| `kg_minimal_contrast` | 9 | 1.000 | 0.486 | 0.486 |
| `kspec_source_rulebook` | 4 | 0.444 | 0.750 | 0.333 |
| `kg_generation_audit` | 3 | 0.333 | 0.458 | 0.153 |
| `trap_ignore_agreement` | 0 | 0.000 | 0.000 | 0.000 |
| `redundant_minimal_probe` | 0 | 0.000 | 0.000 | 0.000 |

Removal delta, averaged across all transforms:

| skill removed | mean accuracy delta |
| --- | ---: |
| `kspec_source_rulebook` | 0.306 |
| `trap_ignore_agreement` | 0.028 |
| `kg_minimal_contrast` | 0.014 |
| `redundant_minimal_probe` | 0.000 |
| `kg_generation_audit` | -0.014 |

Spearman correlation between adoption score and overall removal delta:

```text
0.205
```

Per-transform removal delta for the key skill:

| transform | removing `kspec_source_rulebook` delta |
| --- | ---: |
| `same_world` | 0.750 |
| `composition_swap` | 0.375 |
| `heldout_family` | -0.208 |

Interpretation:

1. The model reliably calls `kg_minimal_contrast`; it also calls
   `kspec_source_rulebook` when the source rulebook looks useful.
2. `kspec_source_rulebook` has high adoption and high overall removal delta,
   but the robust view rejects it: it helps same-world, partially helps
   composition-swap parse, and hurts heldout-family.
3. This is the exact failure mode the project cares about. A naive adoption
   score would promote K_spec. Robust Adoption must check counterfactual /
   held-out removal delta before promotion or distillation.
4. The trap and redundant skills were not called, which is good routing
   behavior, but the sample is still small.

Decision:

- Day 6 validates the need for robust adoption rather than simple call-rate or
  success-conditional adoption.
- The current adoption signal is not reliable enough for GRPO: Spearman is only
  0.205 and K_spec looks attractive unless split by transform.
- Do not train adoption rewards yet. First make the reward robust:
  `same_world` gains count only as provisional; counterfactual/heldout deltas
  decide promotion.

## Overall Decision After Day 4-6

What passed:

1. Trace artifact generation and leakage scan are working.
2. Raw traces are correctly identified as K_spec leakage.
3. Stripped/scrubbed traces have weak but non-leaking heldout gains.
4. Offline adoption exposes the K_spec trap clearly.

What did not pass strongly enough for training:

1. Stripped/scrubbed traces are not yet consistently better than no memory.
2. Adoption score does not yet correlate strongly with causal usefulness.
3. The generic skills are still prose-like. They need executable query/verifier
   structure to become strong K_gen.

Next step:

Do not start SFT or verl yet. The next API-only improvement should be an
executable `K_gen` scaffold:

1. add explicit query/verifier actions or simulated probes to MiniLang;
2. convert stripped trace from advice into action traces;
3. rerun Day 5 and Day 6 with process metrics: query count, verifier count,
   attempts-to-success, and token cost;
4. only then export an SFT/verl manifest.

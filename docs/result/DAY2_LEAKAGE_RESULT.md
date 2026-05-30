# Day 2 Result: Counterfactual Leakage Eval

This file is a factual daily result archive. Protocol and future schedule live in `../EXPERIMENT_PLAN.md`; durable model/environment decisions live in `../MODEL_AND_ENV_REVISIONS.md`.

## Qwen Route Observation

`qwen3.5-27b` is reachable through apihy, but the route defaults to visible
thinking output. Small `max_tokens` values fail because the model spends the
budget on reasoning before producing the final answer.

Failed pattern:

```bash
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model qwen3.5-27b \
  --api-key-env apihy_API_KEY_qwen \
  --base-url-env apihy_BASE_URL \
  --max-tokens 64
```

Working pattern:

```bash
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model qwen3.5-27b \
  --api-key-env apihy_API_KEY_qwen \
  --base-url-env apihy_BASE_URL \
  --max-tokens 64 \
  --extra-body-json '{"enable_thinking": false}'
```

This returns `API_OK` in 20 total tokens. Experiment runners now support
`--extra-body-json`, so Qwen sweeps must pass:

```bash
--extra-body-json '{"enable_thinking": false}'
```

The durable Qwen command pattern is maintained in `../MODEL_AND_ENV_REVISIONS.md`.

Qwen hard-mode smoke after disabling thinking:

| condition | accuracy | parse | generate |
| --- | ---: | ---: | ---: |
| no_scaffold | 0.000 | 0.000 | 0.000 |
| k_spec | 0.875 | 1.000 | 0.750 |
| k_gen | 0.000 | 0.000 | 0.000 |
| k_spec_k_gen | 0.875 | 1.000 | 0.750 |

Qwen leakage smoke, one episode:

| transform | arm | accuracy | parse | generate |
| --- | --- | ---: | ---: | ---: |
| renamed_vocab | source_raw_k_spec | 0.000 | 0.000 | 0.000 |
| renamed_vocab | target_scaffold_k_spec | 0.875 | 1.000 | 0.750 |
| order_swap | source_raw_k_spec | 0.875 | 1.000 | 0.750 |
| order_swap | target_scaffold_k_spec | 0.875 | 1.000 | 0.750 |

Interpretation: Qwen is now usable for this repo, but it should be run with
thinking disabled and enough output budget for JSON.

## DeepSeek Leakage Eval

Combined from:

- `runs/leakage-hard-deepseek-v3_2-smoke2/`
- `runs/leakage-hard-deepseek-v3_2-extra6/`

Seeds: 7-14. Difficulty: hard. Support examples: 8.

| transform | arm | n | accuracy | parse | generate |
| --- | --- | ---: | ---: | ---: | ---: |
| renamed_vocab | source_raw_k_spec | 8 | 0.031 | 0.062 | 0.000 |
| renamed_vocab | target_scaffold_k_spec | 8 | 0.969 | 1.000 | 0.938 |
| order_swap | source_raw_k_spec | 8 | 0.734 | 1.000 | 0.469 |
| order_swap | target_scaffold_k_spec | 8 | 0.969 | 1.000 | 0.938 |

## Interpretation

1. `renamed_vocab` is a strong leakage detector. Source raw K_spec collapses,
   while target scaffold recovers.
2. `order_swap` mainly tests generation, not parsing. Parse remains high because
   the source rulebook still contains the same morpheme-to-meaning mapping, and
   the parse verifier currently checks semantic meaning rather than whether the
   model used the target order rule.
3. This confirms the earlier warning: parse and generation must be reported
   separately. Aggregate accuracy hides the mechanism.
4. Next Day 2 extension: add a transform that swaps morphology composition
   (`count_position`, `color_position`, agreement marker mapping) without only
   renaming the vocabulary. That should test whether models learn the structural
   rule, not just token semantics.

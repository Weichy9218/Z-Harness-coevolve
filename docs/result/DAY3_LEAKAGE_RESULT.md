# Day 3 Result: Stronger Leakage Transforms

This file is a factual daily result archive. Protocol and future schedule live
in `../EXPERIMENT_PLAN.md`; durable model/environment decisions live in
`../MODEL_AND_ENV_REVISIONS.md`.

## What Changed

Day 3 stayed no-training. It added two stronger counterfactual transforms to
`run_leakage`:

- `composition_swap`: keeps lexical stems and count markers but flips
  `color_position`, flips `count_position`, and rotates `agreement_by_count`.
  This tests structural leakage beyond token renaming.
- `heldout_family`: creates a new hard MiniLang family with independent
  vocabulary, morphology, agreement, and order.

`run_leakage` now defaults to:

```bash
--transforms renamed_vocab,order_swap,composition_swap,heldout_family
```

The summary also reports `n`, `total_tokens`, `avg_total_tokens`, and `errors`
per transform/arm.

## Expected Pattern Before Running

| transform | source raw K_spec expectation | target scaffold expectation | Why |
| --- | --- | --- | --- |
| `renamed_vocab` | near 0 | near 1 | source rulebook has wrong surface tokens |
| `order_swap` | parse high, generation lower | near 1 | parse checks semantics; generation needs target order |
| `composition_swap` | parse partially high, generation near 0 | near 1 | lexical semantics stay, but morphology/agreement structure changes |
| `heldout_family` | near 0 | near 1 | source rulebook is unrelated to target family |

The key Day 3 prediction was not that every aggregate score collapses. The key
prediction was sharper: structural transforms should make source raw generation
fail while target scaffold recovers.

## DeepSeek Day 3 Eval

Run:

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_leakage \
  --episodes 8 \
  --difficulty hard \
  --support-budget 8 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --transforms renamed_vocab,order_swap,composition_swap,heldout_family \
  --output-dir runs/day3-leakage-hard-deepseek-v3_2-rerun
```

Artifacts:

- `runs/day3-leakage-hard-deepseek-v3_2-rerun/records.jsonl`
- `runs/day3-leakage-hard-deepseek-v3_2-rerun/summary.json`

Seeds: 7-14. Difficulty: hard. Support examples: 8. API errors: 0.

| transform | arm | n | accuracy | parse | generate | avg tokens | errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `renamed_vocab` | `source_raw_k_spec` | 8 | 0.031 | 0.062 | 0.000 | 1299.25 | 0 |
| `renamed_vocab` | `target_scaffold_k_spec` | 8 | 0.969 | 1.000 | 0.938 | 1300.12 | 0 |
| `order_swap` | `source_raw_k_spec` | 8 | 0.750 | 1.000 | 0.500 | 1300.75 | 0 |
| `order_swap` | `target_scaffold_k_spec` | 8 | 0.969 | 1.000 | 0.938 | 1301.25 | 0 |
| `composition_swap` | `source_raw_k_spec` | 8 | 0.453 | 0.875 | 0.031 | 1288.00 | 0 |
| `composition_swap` | `target_scaffold_k_spec` | 8 | 1.000 | 1.000 | 1.000 | 1305.00 | 0 |
| `heldout_family` | `source_raw_k_spec` | 8 | 0.078 | 0.156 | 0.000 | 1305.25 | 0 |
| `heldout_family` | `target_scaffold_k_spec` | 8 | 0.984 | 1.000 | 0.969 | 1286.88 | 0 |

## Gap Analysis

### 1. Main expectation passed

`composition_swap` did what Day 3 needed: source raw generation collapsed from
the Day 2 `order_swap` level of 0.500 to 0.031, while target scaffold reached
1.000. This means the new transform is measuring structural rule leakage, not
only lexical token leakage.

`heldout_family` also behaved as expected: source raw generation was 0.000 and
aggregate accuracy was 0.078, while target scaffold recovered to 0.984.

### 2. `composition_swap` source raw parse stayed high

Expected direction: parse might remain partially high. Actual: parse was 0.875,
which is higher than a strict "source raw should collapse" reading.

Reason:

- `composition_swap` intentionally preserves token-to-concept stems and count
  markers.
- The target prompt still includes target examples.
- The parse verifier checks semantic meaning, not whether the model used the
  target structural rule.

So this is not a failure of `composition_swap`; it tells us the transform is
mainly a generation-side structural leakage test. Aggregate accuracy is
misleading here. For this transform, generation accuracy is the primary metric.

### 3. `order_swap` remains weak as a structural detector

`order_swap` source raw aggregate accuracy stayed 0.750 because parse was 1.000
and generation was still 0.500. This confirms the Day 2 interpretation:
changing phrase order alone is not enough to strongly penalize source raw
memory when target examples and lexical mappings still reveal semantics.

Use `order_swap` as a lightweight generation check, not as the main leakage
detector.

### 4. Target scaffold was not perfectly 1.0 in every transformed family

Target scaffold had small generation errors in `renamed_vocab`, `order_swap`,
and `heldout_family`. Inspection shows exact morphology slips, e.g. using the
wrong color/count morpheme in one generated command. Parse was 1.000 throughout.

Likely cause:

- model execution error on exact surface generation, not API failure;
- no runner errors occurred;
- the failures are isolated generation slips despite the correct target
  rulebook being present.

This means target scaffold should be treated as a high but imperfect upper
bound for API-model runs. For later trace/SFT evaluation, report confidence
intervals or increase episode count rather than assuming oracle scaffold equals
1.0.

## Decision

Day 3 passes its gate.

The measurement protocol now has:

1. lexical leakage detector: `renamed_vocab`;
2. weak phrase-order detector: `order_swap`;
3. structural generation detector: `composition_swap`;
4. broad held-out family detector: `heldout_family`.

Next step should be Day 4: generate raw / stripped / artifact-scrubbed trace
datasets, with an automatic leakage scanner. Do not start SFT or verl yet.

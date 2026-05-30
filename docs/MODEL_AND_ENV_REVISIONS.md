# Model and Environment Revision Notes

## Why Day 1 Was Too Easy

The first MiniLang environment was a useful plumbing test, but not a good
scientific test:

- The surface form was mostly independent tokens with one global word order.
- Twelve examples exposed most latent concepts.
- `gpt-5.4` was too strong for the task.
- `K_gen` was only prompt advice, not an actual query/verifier scaffold.

Therefore the original Day 1 table should be treated as an infrastructure smoke
test, not evidence for scaffold distillation.

## Model Change

Do not use GPT-family models for the main v0 sweeps. Current API commands:

```bash
# Qwen through apihy
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model qwen3.6-27b \
  --api-key-env apihy_API_KEY_qwen \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none

# DeepSeek through apihy
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none
```

Observed:

- `deepseek-v3.2` is stable enough for daily sweeps.
- `qwen3.6-27b` answers short smoke prompts and hard-mode `k_spec`, but hard
  no-scaffold requests can hang for minutes on the current route. Use it for
  targeted cells until route latency is diagnosed.
- `qwen3.5-27b` is usable only after disabling visible thinking with
  `--extra-body-json '{"enable_thinking": false}'`. Without that, it spends the
  completion budget on visible reasoning and may never emit final JSON.

## Environment Change

Lingojam-style alien translators are useful as inspiration, but not as the
benchmark itself: the public page exposes a generated alien-looking surface form
and UI, not a stable hidden grammar/verifier. The v0 environment should remain
programmatic.

`--difficulty hard` now uses an AlienGlyph-style morphology:

- object phrase is hyphenated morphology over color, object, and count marker;
- action phrase has action stem plus count agreement marker;
- negative commands include a neg token;
- word order changes under negation;
- generation requires exact surface form, not just semantic parsing.

Run:

```bash
python -m zharness.eval.run_headroom \
  --episodes 8 \
  --difficulty hard \
  --support-budget 8 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none
```

## Hard-Mode DeepSeek Result

Combined from `runs/hard-deepseek-v3_2-smoke2/` and
`runs/hard-deepseek-v3_2-extra6/`, seeds 7-14:

| condition | n | accuracy | parse | generate |
| --- | ---: | ---: | ---: | ---: |
| no_scaffold | 8 | 0.250 | 0.219 | 0.281 |
| k_spec | 8 | 0.969 | 1.000 | 0.938 |
| k_gen | 8 | 0.234 | 0.219 | 0.250 |
| k_spec_k_gen | 8 | 1.000 | 1.000 | 1.000 |

Interpretation:

1. Hard mode has real scaffold headroom.
2. `K_spec` is a strong oracle and should remain the headroom upper bound.
3. Current `K_gen` is not an effective scaffold; it is neutral or harmful.
4. The next valid `K_gen` must be executable/interactive: query selection,
   verifier calls, counterexample construction, and repair, not only prose.

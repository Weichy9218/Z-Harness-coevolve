# Model and Environment Revision Notes

## 责任边界

本文件只记录 durable 的模型路由、API quirks、环境设计修改和可复用命令。数值结果、run artifacts、当日解释放在 [docs/result/](result/)，避免同一张表在多个文件漂移。

## Why Day 1 Was Too Easy

The first MiniLang environment was a useful plumbing test, but not a good scientific test:

- The surface form was mostly independent tokens with one global word order.
- Twelve examples exposed most latent concepts.
- `gpt-5.4` was too strong for the task.
- `K_gen` was only prompt advice, not an actual query/verifier scaffold.

Therefore the original Day 1 table is infrastructure validation only, not evidence for scaffold distillation. The current v0 sweeps should use hard MiniLang plus apihy Qwen/DeepSeek routes.

## Model Policy

Do not use GPT-family models for the main v0 sweeps. GPT calls are allowed only as plumbing smoke checks when diagnosing the runner itself.

Observed route status:

- `deepseek-v3.2` through apihy is stable enough for daily sweeps.
- `qwen3.5-27b` through apihy is usable after disabling visible thinking with `--extra-body-json '{"enable_thinking": false}'`.
- `qwen3.6-27b` is reachable, but hard no-scaffold requests can hang for minutes on the current route. Keep testing targeted cells because Qwen is the intended future training model.

Small `max_tokens` was not the root cause of Qwen failure by itself. The failure mode was visible thinking consuming the completion budget before final JSON. For Qwen experiment runs, use both:

- `--max-tokens 1024` or larger for task sweeps
- `--extra-body-json '{"enable_thinking": false}'`

## API Smoke Commands

DeepSeek:

```bash
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none
```

Qwen:

```bash
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model qwen3.5-27b \
  --api-key-env apihy_API_KEY_qwen \
  --base-url-env apihy_BASE_URL \
  --max-tokens 64 \
  --extra-body-json '{"enable_thinking": false}'
```

Hard-mode sweep default:

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

Qwen hard-mode targeted sweep:

```bash
python -m zharness.eval.run_headroom \
  --episodes 1 \
  --difficulty hard \
  --support-budget 8 \
  --client openrouter_newapi \
  --model qwen3.5-27b \
  --api-key-env apihy_API_KEY_qwen \
  --base-url-env apihy_BASE_URL \
  --max-tokens 1024 \
  --extra-body-json '{"enable_thinking": false}'
```

## Environment Change

Lingojam-style alien translators are useful as inspiration, but not as the benchmark itself: the public page exposes a generated alien-looking surface form and UI, not a stable hidden grammar/verifier. The v0 environment should remain programmatic.

`--difficulty hard` now uses an AlienGlyph-style morphology:

- object phrase is hyphenated morphology over color, object, and count marker;
- action phrase has action stem plus count agreement marker;
- negative commands include a neg token;
- word order changes under negation;
- generation requires exact surface form, not just semantic parsing.

The next environment revision should add a structural counterfactual transform, either `morphology_swap` or `agreement_swap`, because current `order_swap` mostly exposes generation errors while semantic parse can remain high.

## Result Pointers

- Day 1 scaffold headroom and hard-mode DeepSeek table: [docs/result/DAY1_RESULT.md](result/DAY1_RESULT.md)
- Day 2 leakage eval and Qwen route observation: [docs/result/DAY2_LEAKAGE_RESULT.md](result/DAY2_LEAKAGE_RESULT.md)

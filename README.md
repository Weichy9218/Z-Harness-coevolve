# Z-Harness-coevolve

实验目标：研究 agent 通过 scaffold / skill 解决隐藏规则任务后，哪些经验应该留在 harness/skill，哪些可以蒸馏进 weights，哪些必须 quarantine/forget。

当前 v0 只做 no-GPU、API-only 的 MiniLang 实验，先验证三个最小问题：

1. Scaffold 是否降低 learning cost。
2. Raw trace 和 stripped trace 是否能被 counterfactual transforms 区分。
3. Adoption signal 是否能预测 skill 的 causal usefulness。

## Quick Start

`.env` 已从 `galaxy-selfevolve` 复制到本 repo 根目录，但被 `.gitignore` 排除，不会提交。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

先跑 deterministic smoke test：

```bash
python -m pytest
python -m zharness.eval.run_headroom --episodes 2 --mock-policy oracle
```

检查 API 是否可用：

```bash
python scripts/check_llm.py --client gpt_sub2api --model gpt-5.4
```

跑第一批 API scaffold headroom。主 sweep 不再默认用 GPT；当前建议用 apihy DeepSeek hard mode：

```bash
python -m zharness.eval.run_headroom \
  --episodes 8 \
  --difficulty hard \
  --support-budget 8 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --conditions no_scaffold,k_spec,k_gen,k_spec_k_gen
```

输出会写到 `runs/minilang_headroom/`。

## Project Layout

```text
core/llm/                    # copied from galaxy-selfevolve
docs/EXPERIMENT_PLAN.md      # paper-facing experiment plan
docs/DAILY_PLAN.md           # compressed daily execution plan
zharness/envs/minilang/      # synthetic hidden-rule language environment
zharness/agents/             # LLM wrappers and answer parsing
zharness/eval/               # runnable evaluation scripts
scripts/check_llm.py         # API smoke check
tests/                       # deterministic tests
```

## Current Scope

This repo intentionally starts smaller than a full co-evolve system. The first milestone is a reproducible MiniLang scaffold-headroom result with API calls only. LoRA/GRPO, MiniAPI, AppWorld, and Terminal-Bench are v1+ after the measurement protocol is stable.

See [docs/MODEL_AND_ENV_REVISIONS.md](docs/MODEL_AND_ENV_REVISIONS.md) for why the original GPT/basic MiniLang run is only a smoke test and why hard-mode DeepSeek is the current default.

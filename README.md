# Z-Harness-coevolve

研究目标：把 agent 成功经验分配到正确位置。一次 scaffold / skill 帮助模型解决隐藏规则任务后，需要判断哪些经验应该留在 harness/skill，哪些可以 distill 到 weights，哪些必须 quarantine/forget。

当前判断：不要先做 Hanabi -> Terminal-Bench 2，也不要先写完整 co-evolve 大系统。v0 先在可控、可验证、可做 counterfactual 的 MiniLang / MiniAPI 中打穿三个问题：

1. **Scaffold headroom**：scaffold 是否真的降低 learning cost。
2. **Trace abstraction**：stripped trace 是否比 raw trace 更能迁移、更少泄漏。
3. **Adoption causality**：adoption signal 是否能预测 skill / harness item 的 causal usefulness。

如果这三项至少两项成立，再进入 SFT / verl / GRPO / AppWorld / Terminal-Bench 2。否则先修环境、trace abstraction 或 skill routing，不急着烧 8 张 A100。

## Scientific Contract

核心对象是 experience allocation：`K_spec` quarantine，`K_gen` 进入 skill/harness，真正泛化的 `theta` 才能进入 weights。完整判据和 daily checkpoint 只维护在 [docs/EXPERIMENT_PLAN.md](docs/EXPERIMENT_PLAN.md)。

## Current Evidence

MiniLang hard mode 已经有 scaffold headroom，Day 2 leakage smoke 也支持当前 measurement：`renamed_vocab` 会让 source raw K_spec 崩掉，而 target scaffold 恢复；`order_swap` 主要影响 generation，说明 parse/generate 必须分开报。

具体表格只维护在 result archive，避免 README 和 docs 漂移：

- [Day 1 scaffold headroom](docs/result/DAY1_RESULT.md)
- [Day 2 leakage eval](docs/result/DAY2_LEAKAGE_RESULT.md)
- [Model and environment notes](docs/MODEL_AND_ENV_REVISIONS.md)

## Quick Start

`.env` 已从 `galaxy-selfevolve` 复制到本 repo 根目录，但被 `.gitignore` 排除，不会提交。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Deterministic smoke test：

```bash
python -m pytest
python -m zharness.eval.run_headroom --episodes 2 --mock-policy oracle
```

API smoke：

```bash
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none
```

主线 hard-mode headroom sweep：

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

Counterfactual leakage sweep：

```bash
python -m zharness.eval.run_leakage \
  --episodes 8 \
  --difficulty hard \
  --support-budget 8 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --transforms renamed_vocab,order_swap
```

Qwen through apihy needs visible thinking disabled:

```bash
python -m zharness.eval.run_headroom \
  --episodes 1 \
  --difficulty hard \
  --client openrouter_newapi \
  --model qwen3.5-27b \
  --api-key-env apihy_API_KEY_qwen \
  --base-url-env apihy_BASE_URL \
  --max-tokens 1024 \
  --extra-body-json '{"enable_thinking": false}'
```

Run artifacts are written under `runs/`.

## Documentation Map

- [docs/EXPERIMENT_PLAN.md](docs/EXPERIMENT_PLAN.md)：paper-facing scientific plan, metrics, falsifiers, stage gates.
- [docs/TRAINING_PLAN.md](docs/TRAINING_PLAN.md)：SFT / verl / GRPO plan for the 8xA100 server phase.
- [docs/RELATED_EXPERIMENTS.md](docs/RELATED_EXPERIMENTS.md)：SAGE、Meta-Harness、SIA、Harness-Bench、AppWorld、tau-bench、Terminal-Bench 2、verl 的定位。
- [docs/MODEL_AND_ENV_REVISIONS.md](docs/MODEL_AND_ENV_REVISIONS.md)：model routing and MiniLang environment notes.
- [docs/result/](docs/result/)：daily factual result archives.

## Project Layout

```text
core/llm/                    # copied from galaxy-selfevolve
docs/                        # experiment design, training route, related work, result notes
zharness/envs/minilang/      # synthetic hidden-rule language environment
zharness/agents/             # LLM wrappers, prompts, answer parsing
zharness/eval/               # runnable evaluation scripts
scripts/check_llm.py         # API smoke check
tests/                       # deterministic tests
```

## Scope Control

v0 is intentionally no-training and API-only. The first deliverable is not a big self-improving system; it is a clean measurement protocol showing that:

1. `K_spec` gives real headroom.
2. Counterfactual transforms catch leakage.
3. Robust adoption correlates with counterfactual removal delta.

Training starts only after trace quality and leakage tests are stable. The server phase should support both SFT and verl, but raw trace SFT is a control arm, not the intended method.

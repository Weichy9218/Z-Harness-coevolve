# Z-Harness-coevolve

本仓库现在只服务一个目标：打通 HarnessX 风格的 harness/model co-evolution 闭环，优先落在 Terminal-Bench 2.1 上。

旧的 MiniLang/MiniAPI synthetic scaffold-adoption 路线已经归档。它留下的有用经验是：raw trajectory 容易把 task-specific facts 带进训练，必须保留 split、leakage scan、removal ablation 和 held-out gate。但它不再是本项目主线。

## Current Direction

核心判断：

1. **HarnessX 是基础设施主线。** 我们要复用 `Harness.run(task) -> trajectory/reward -> HarnessConfig evolution -> training records -> model update` 的闭环，而不是继续维护自造 synthetic harness。
2. **Terminal-Bench 2.1 是第一个主 benchmark。** 官方 leaderboard 当前使用 `terminal-bench/terminal-bench-2-1`；2.0 只保留为历史 smoke/迁移对照，不再作为主线。
3. **先 harness-only，再 model update。** 本地先跑 HarnessX + Harbor + Terminal-Bench smoke；服务器 8xA100 再训练 Qwen 8B LoRA/SFT/GRPO。
4. **外部 benchmark 分层使用。** τ³-bench text domains 是下一批 text-agent transfer target；WebArena 和 BALROG 做泛化压力测试；HCAST 和 METR-HRS 做 held-out calibration，不进频繁优化 loop。

## Documentation Map

- [docs/README.md](docs/README.md): 文档入口。
- [docs/DIRECTION.md](docs/DIRECTION.md): 新目标、旧路线为什么停、done criteria。
- [docs/HARNESSX_SIA_FLOW.md](docs/HARNESSX_SIA_FLOW.md): HarnessX 与 SIA 的流程对应和闭环设计。
- [docs/BENCHMARK_STRATEGY.md](docs/BENCHMARK_STRATEGY.md): Terminal-Bench、WebArena、BALROG、HCAST、METR-HRS 的分层使用。
- [docs/TERMINAL_BENCH_2_PLAN.md](docs/TERMINAL_BENCH_2_PLAN.md): Terminal-Bench 2.1 优先实现路线。
- [docs/QWEN8B_TRAINING_PLAN.md](docs/QWEN8B_TRAINING_PLAN.md): 8xA100 上 Qwen 8B 的训练计划。
- [docs/SMOKE_RESULTS.md](docs/SMOKE_RESULTS.md): 本地 smoke 结果和迁移证据。
- [docs/archive/PRIOR_RESULTS_SUMMARY.md](docs/archive/PRIOR_RESULTS_SUMMARY.md): 旧 MiniLang/MiniAPI 代表性结果摘要。
- [docs/SOURCES.md](docs/SOURCES.md): 关键外部和本地资料来源。

## Local State

本机已有 HarnessX clone：

```text
/Users/weichy/code/HarnessX
/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2
```

本机已跑通 Harbor + Docker + Terminal-Bench 2.1 oracle smoke。下一步是在 HarnessX 仓库里跑 2.1 HarnessXAgent smoke，再决定是否把自动化 wrapper 放回本仓库。

## Quick Checks

本仓库保留 API route smoke：

```bash
python scripts/check_llm.py \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none
```

方向文档检查：

```bash
.venv/bin/python -m pytest
```

Terminal-Bench smoke 在 HarnessX 仓库执行，详见 [docs/TERMINAL_BENCH_2_PLAN.md](docs/TERMINAL_BENCH_2_PLAN.md)。

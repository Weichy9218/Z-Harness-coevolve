# Docs

本目录是当前项目的系统记录。主线已经切换到 HarnessX-first，不再维护 MiniLang/MiniAPI synthetic experiment 的 daily docs。

## Reading Order

1. [DIRECTION.md](DIRECTION.md): 项目目标和边界。
2. [HARNESSX_SIA_FLOW.md](HARNESSX_SIA_FLOW.md): HarnessX/SIA 的流程抽象。
3. [BENCHMARK_STRATEGY.md](BENCHMARK_STRATEGY.md): benchmark 分层。
4. [TERMINAL_BENCH_2_PLAN.md](TERMINAL_BENCH_2_PLAN.md): 当前最优先执行项，已切到 Terminal-Bench 2.1。
5. [QWEN8B_TRAINING_PLAN.md](QWEN8B_TRAINING_PLAN.md): 服务器训练阶段。
6. [SMOKE_RESULTS.md](SMOKE_RESULTS.md): 本地 smoke 结果和迁移证据。
7. [archive/PRIOR_RESULTS_SUMMARY.md](archive/PRIOR_RESULTS_SUMMARY.md): 旧路线留下的代表性证据。
8. [SOURCES.md](SOURCES.md): 外部来源和本地证据。

## Maintenance Rule

新增结论只写进上面的主文档之一。`runs/` 只放可删除的本地运行产物；paper-facing 的事实、命令、版本、split 和结论必须落在 tracked docs 中。

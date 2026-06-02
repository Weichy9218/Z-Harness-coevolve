# 01 系统架构

## 目标

本项目现在的核心不是 MiniLang，也不是直接训练一个大模型。核心目标是：

> 复现并验证 HarnessX 在 Terminal-Bench 2.1 和后续 tau-bench 上的 harness-only 改进，再决定哪些成功轨迹可以安全进入训练。

也就是说，当前先回答：

1. 同一个模型 `M0=deepseek-v3.2` 下，改 harness 是否真的能提升 benchmark 表现。
2. 这些 harness 改动是否是通用机制，而不是某个 task 的答案提示。
3. 哪些轨迹可以作为训练数据，哪些必须排除。

## 当前方法

当前方法是 HarnessX-first：

```text
固定模型 M0
  -> 在 HarnessX 上跑 Terminal-Bench 2.1
  -> 读取 result.json / verifier / oh_runs / processor trace
  -> 标注 failure mechanism
  -> 只改通用 harness policy
  -> 加 regression test
  -> 先跑 single-task gate
  -> 再跑 same-split dev ablation
  -> 冻结 H*
  -> 只收 train split 成功轨迹
  -> sanitizer/export
  -> 再考虑 SFT / LoRA / GRPO
```

## Repo 分工

`/Users/weichy/code/HarnessX` 是 runnable substrate：

- benchmark integration；
- Terminal-Bench / tau-bench runner；
- harness processors；
- Docker / sandbox 行为；
- execution trajectory 和 verifier interaction。

`/Users/weichy/code/Z-Harness-coevolve` 是 experiment controller：

- split manifest；
- run ledger；
- result summary；
- export / sanitization policy；
- 训练前 readiness 决策；
- 文档和计划。

不要把 Terminal-Bench 或 tau-bench 数据 vendoring 到 Z repo。

## 当前代码重点

Z repo 中当前和核心主线相关的是：

```text
experiments/tb2_1_harness_only/run_ledger.json
splits/terminal_bench_2_1/
scripts/tb2_summarize_job.py
scripts/tb2_export_sft_candidates.py
zharness/tb2/pretrain_prep.py
tests/test_tb2_pretrain_prep.py
```

`zharness/envs/minilang/` 可以保留历史结果和代码，但不是当前主线。

## 模型与环境

当前 TB2 route：

```bash
export TB2_MODEL=deepseek-v3.2
export TB2_API_BASE=https://zgc.apihy.com/v1
export TB2_API_KEY="$apihy_API_KEY_deepseek"
```

`TB2_API_KEY` 是模型接口 key。它对应 `.env` 里的
`apihy_API_KEY_deepseek`，不是 Terminal-Bench 数据集 key。

当前 sandbox：

- HarnessX local Docker；
- `DinDDockerEnvironment`；
- `network_mode=host`。

比较 H0/M0 与 H*/M0 时，必须固定 model route、sandbox、split、max steps、
request timeout 和 concurrency。

## 当前状态

- H2 harness patch 已在 HarnessX 本地实现。
- HarnessX targeted tests 已通过：`26 passed`。
- Z repo tests 已通过：`18 passed`。
- H2c 因 small literal probe false positive 被标为 invalid。
- H2d 因 hash-string false positive 被标为 invalid。
- H2e real gate 已从 `.env` 读取 `apihy_API_KEY_deepseek` 后完成：
  reward `0.0`，无 infra exception，但 verifier 缺 `/app/solution.txt`。
- H3 failure-mechanism patch 已在 HarnessX 本地实现并提交：
  `61977b7 Add TB2 H3 failure-mechanism guards`。
- H3 初次 run 暴露 BuildInstallLoopGuard false positive，并且 oh_runs
  `task_end` 有 `APIConnectionError`，标为 invalid diagnostic。
- H3b 修复后 real gate 已完成：reward `0.0`，无 infra exception，
  agent `exit_reason=budget_exceeded`，verifier 仍缺 `/app/solution.txt`。
  H3b 是 clean gate failure，但不是训练或 dev ablation 的充分信号。

训练还不能开始。H3b 说明 repeated bounded probe、build/install loop 和 final
output self-verify 机制可以干净介入，但仍不足以让 `crack-7z-hash` 成功。下一步
不应直接跑 10-task dev ablation，而应先针对 H3b 的 post-guard strategy deadlock
设计 H4/H3c 级别的机制补丁或明确放弃该单任务路径。

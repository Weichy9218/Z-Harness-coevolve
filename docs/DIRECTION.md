# Direction Reset: HarnessX-First Co-Evolution

## Actual Objective

本项目现在要回答的问题不是“synthetic scaffold 能否被抽象成安全 memory”，而是：

> 能否在真实 agent benchmark 上，用 HarnessX 打通 harness evolution 和 model evolution 的闭环，并用严格 split/ablation 证明收益来自可复用 harness 或可泛化 model update，而不是 benchmark overfitting。

第一个主 benchmark 是 Terminal-Bench 2.1，版本 pin 为 `terminal-bench/terminal-bench-2-1`。

## Why The Previous Direction Stops

MiniLang/MiniAPI 的价值是 protocol proof：它证明了 raw trace leakage、counterfactual transfer 和 robust adoption gate 的必要性。但它已经不再回答当前最重要的问题：

- 它不覆盖真实 terminal workflow、Docker/container、长程调试、服务保持、文件系统状态和 verifier timeout。
- 它的 symbolic executor 太干净，不能暴露 HarnessX 真正要解决的 processor/tool/memory/control 问题。
- 继续迭代 synthetic harness 会推迟核心交付：HarnessX + Terminal-Bench + Qwen 8B 训练闭环。

因此旧代码和 run artifacts 被清理；代表性结论保留在 [archive/PRIOR_RESULTS_SUMMARY.md](archive/PRIOR_RESULTS_SUMMARY.md)。

## Target System

目标闭环：

```text
Terminal-Bench 2.1 task + Harbor container + verifier
  -> HarnessX HarnessConfig + model rollout
  -> trajectory / reward / failure taxonomy
  -> harness-only proposal and accept/revert gate
  -> accepted H*
  -> training records from H* rollouts
  -> Qwen 8B LoRA/SFT/GRPO update on 8xA100
  -> 2x2 ablation: H0/M0, H*/M0, H0/M*, H*/M*
  -> held-out evaluation on frozen splits
```

## Invariants

- Version pinning: Terminal-Bench paper experiments use `terminal-bench/terminal-bench-2-1`.
- Split discipline: train/dev/test split is fixed before harness/model optimization.
- No test leakage: HCAST/METR-HRS are calibration/evaluation only unless explicitly re-scoped.
- Trajectory hygiene: training records must keep model messages/tool outputs/rewards, but must strip benchmark-specific solution leakage when converted to reusable instruction data.
- One active path: HarnessX/Terminal-Bench is the active route; MiniLang/MiniAPI is archive only.
- Transfer benchmarks are not part of the inner loop by default. τ³-bench text domains may be added after the Terminal-Bench 2.1 dev split is stable.

## Done Criteria

Phase 0 is done when:

- HarnessX local clone can run a Terminal-Bench 2.1 dry-run and one real task.
- Outputs include Harbor job dir, HarnessX journal traces, reward/result files, and a small failure taxonomy.
- Docs record exact command, model route, sandbox backend, task list, and failure modes.

Phase 1 is done when:

- H0 baseline on a fixed Terminal-Bench 2.1 dev split is reproducible.
- At least one harness-only change is accepted by a predeclared score gate.
- Reverted changes are logged with reason.

Phase 2 is done when:

- Qwen 8B LoRA/SFT or GRPO is trained from accepted trajectories on 8xA100.
- The 2x2 ablation separates harness-only gain from model-only gain.
- Held-out Terminal-Bench and at least one transfer benchmark are reported without feeding test trajectories back into training.

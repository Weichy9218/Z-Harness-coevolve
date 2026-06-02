# 02 相关工作

## SIA

SIA 的核心是同时做 harness update 和 weight update。它的启发是：

- 失败后不一定训练模型，也可以更新 harness；
- feedback agent 需要根据 failure mode 选择更新类型；
- LoRA adapter 可以作为 weight update unit。

本项目借用 SIA 的 outer-loop framing，但当前阶段只允许 harness update。
原因是：如果 harness-only gain 还没证明，直接训练会把环境噪声、错误策略或
task-specific artifacts 写进 weights。

## Meta-Harness

Meta-Harness 搜索 harness code，并保存 source、score、trace、failure notes。

本项目借用：

- artifact-backed diagnosis；
- 基于历史 failure mechanism 改 harness；
- 保存 execution trace，而不是只保存 scalar score；
- 把 model-harness pair 当作报告单位。

本项目暂时不做 unconstrained harness search。当前 H1/H2 都必须是可解释、
通用、可回归测试的 harness policy。

## Harness-Bench

Harness-Bench 的重要点是：能力应该报告在 model-harness configuration 上。

本项目采用这个口径：

- H0/M0：baseline harness + fixed model；
- H*/M0：modified harness + same fixed model；
- 只比较同模型、同 sandbox、同 split、同 budget。

这能避免把 harness 的收益误记成 base model 的能力。

## Terminal-Bench 2

Terminal-Bench 2 是当前主 benchmark。它适合测试：

- command-line agent；
- install / dependency recovery；
- long-horizon tool use；
- verifier-driven final artifact；
- tool-cost control；
- sandbox/runtime robustness。

当前任务不是“刷 TB2 分数”，而是先证明 HarnessX 的通用 policy 改动能在固定
split 上带来 harness-only gain。

## tau-bench / tau3-bench

tau-bench 是后续 transfer check，不是当前第一个 inner loop。

它适合测试：

- multi-turn user-agent interaction；
- domain-specific API tools；
- policy guideline following；
- final database state；
- pass^k 稳定性。

计划是在 TB2 H* 冻结后，把 TB2 学到的通用 harness discipline 迁移到 tau-bench，
看是否也能改善 tool-use consistency 和 policy compliance。

## verl / GRPO

verl 是后续训练阶段可能使用的框架，尤其是 agentic RL / GRPO / LoRA。

但它只能在以下条件满足后使用：

- H* 已冻结；
- train split 和 heldout split 分离；
- 只有 accepted successful train trajectories 进入数据；
- sanitizer 和 sampled human review 通过；
- reward 和 evaluator 足够稳定。

否则 GRPO 只会放大 harness loop 里的 artifact。

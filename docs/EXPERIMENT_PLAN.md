# 论文实验规划：Quarantined Skill Adoption

## 目标

不是先证明一个完整 co-evolve 大系统，而是先用便宜、可控、可验证的环境回答三个问题：

1. **Scaffold headroom**：scaffold / skill 是否真的降低 learning cost。
2. **Trace abstraction**：stripped trace 是否比 raw trace 更少泄漏、更能迁移。
3. **Adoption causality**：adoption signal 是否能预测 skill / harness item 的 causal usefulness。

核心 claim：

> 只有在 counterfactual / held-out 条件下仍然有 causal usefulness 的 scaffold experience，才允许进入 reusable skill 或 weights；K_spec 必须 quarantine。

## 经验分配表

| 经验类型 | 去向 | 实验判据 |
| --- | --- | --- |
| K_spec：当前词表、隐藏规则、题目答案、API 私有 contract | nowhere / quarantined | renamed / rule swap 后收益消失；进入 weights 算 leakage |
| K_gen：主动查询、rule induction、边界测试、verifier 使用、repair pattern | harness / skill，部分可蒸馏 | held-out family 上降低 learning cost |
| theta：验证驱动、错误恢复、规则归纳习惯 | weights | no-specific-harness eval 仍提升 |

## Experiment A：MiniLang Scaffold Headroom

环境：随机生成 alien surface form、word order、negation token、action/object/color/count 组合规则。默认用 `--difficulty hard`：对象短语由 color/object/count marker 组成 hyphenated morphology，动作短语带 count agreement，negation 会改变 word order。每个 episode 给少量 labeled examples，模型完成 parse 和 generate 两类任务。

条件：

| 条件 | 给模型什么 | 目的 |
| --- | --- | --- |
| `no_scaffold` | 只有 examples 和 tasks | 基线 |
| `k_spec` | 当前 rulebook：词表和 word order | 测 task-specific scaffold 上限 |
| `k_gen` | 通用 discovery playbook | 测 general scaffold 是否可用 |
| `k_spec_k_gen` | 两者都给 | 测 scaffold 上限 |

指标：

- success / parse accuracy / generation accuracy
- token usage
- task-level failure cases
- 后续加入 attempts-to-success、query calls、verifier calls

Kill conditions：

- `k_spec` 不显著强于 `no_scaffold`：任务或 prompt 设计失败。
- `k_gen` 没有 learning-cost 收益：playbook 太空，模型用不上。
- parse/generate 不拆开时结论变化：aggregate metric 不可信。

## Experiment B：Raw Trace vs Stripped Trace

训练数据从 scaffolded successful episodes 生成两份：

Raw trace 保留：

- 当前词表
- 当前 grammar
- 当前答案
- 具体 rule names

Stripped trace 保留：

- hypothesis formation
- minimal contrast query
- verifier feedback use
- repair pattern
- answer checking procedure

评测：

- seen family
- renamed vocab
- order/rule swap
- held-out grammar family
- no-specific-harness

指标：

- Internalization Gain
- Leakage Susceptibility
- Harness Dependence Ratio

Kill conditions：

- raw 和 stripped 没区别：leakage transform 太弱，或 abstraction 没抽出有效策略。
- stripped 在 no-specific-harness 下不提升：没有 internalization。

## Experiment C：Offline Adoption Signal

先不做 GRPO。构造 frozen skill library，混入：

- good K_gen skill
- K_spec leakage skill
- description trap skill
- redundant skill

每题最多调用 k 个 skill，记录：

- `call(s, tau)`
- task reward
- success conditional rate
- non-invocation
- novelty / age

然后做 counterfactual removal：逐个删除 skill，看 success delta。

主判据：

- adoption score 与 removal delta 的 Spearman correlation。
- high-adoption 但 counterfactual 崩的 skill 判为 K_spec，不允许蒸馏。

## Experiment D：MiniAPI / ToolWorld

迁移到 agentic setting：生成 API schema，并隐藏 constraints：

- 参数互斥
- 状态依赖
- 错误码语义
- 调用顺序
- 权限限制
- rollback 条件

复用 A/B/C 三套实验。

Process metrics 借 Harness-Bench：

- completion
- robustness
- tool use
- consistency
- forbidden action rate
- token/tool/verifier cost

## Later Validation

外部验证顺序：

1. MiniLang family A -> MiniLang family B
2. MiniLang -> MiniAPI
3. MiniAPI -> AppWorld / tau-bench
4. Terminal-Bench 2 only as secondary validation

Hanabi -> Terminal-Bench 2 只适合后期 headline transfer，不适合 v0。

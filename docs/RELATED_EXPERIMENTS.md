# Related Work and Borrowed Protocols

调研日期：2026-05-30。这里记录的是本项目要借什么、不借什么，以及如何避免和相邻工作混在一起。

## SAGE: Skill Augmented GRPO

Source: [Reinforcement Learning for Self-Improving Agent with Skill Library](https://arxiv.org/abs/2512.17102)

Relevant facts：

- SAGE 用 Sequential Rollout：agent 在相似任务链上 rollout，前面任务生成的 skills 对后续任务可用。
- 它把 skill-integrated reward 加到 outcome reward 之外，用于 skill generation / utilization。
- AppWorld 结果报告：在 expert SFT 后使用 SAGE，Scenario Goal Completion 提升 8.9%，interaction steps 降低 26%，tokens 降低 59%。

Borrow：

- sequential rollout；
- skill library 在后续任务中可用；
- SAGE-like baseline：`M=2`、unbounded library、二元“后续任务用了且成功”reward。

Do not borrow as main claim：

- 不把 AppWorld success 当主指标，否则会变成 another skill-library RL paper。
- 不把“被调用且成功”直接当可蒸馏信号；必须加 counterfactual removal 和 leakage transforms。

Our delta：

- SAGE 证明 skill library + RL 可以提升 agent；我们问 high-adoption skill 是否真的 causal、是否 robust、是否允许进入 weights。

## Meta-Harness

Source: [Meta-Harness: End-to-End Optimization of Model Harnesses](https://arxiv.org/abs/2603.28052), [project page](https://yoonholee.com/meta-harness/)

Relevant facts：

- Meta-Harness 搜索 harness code，而不是只优化 prompt。
- Proposer 能读取 prior candidates 的 source code、scores、execution traces。
- 报告了 online text classification、retrieval-augmented math reasoning、TerminalBench-2 上的 harness gains。

Borrow：

- trace filesystem；
- 每轮保存 source、scores、trajectories、failure notes；
- proposer 基于历史 failure mechanism 改 harness；
- 不把 trace 压缩到只剩一个 scalar score。

Do not borrow as v0 environment：

- Terminal-Bench 2 太贵、太 noisy、失败归因难。v0 用 MiniLang / MiniAPI 建因果证据，再考虑把 Meta-Harness-style trace filesystem 接进来。

Our delta：

- Meta-Harness 优化 harness；我们额外决定哪些 experience 可留在 harness，哪些可进 weights，哪些必须 quarantine。

## SIA: Harness and Weight Updates

Source: [SIA: Self Improving AI with Harness & Weight Updates](https://arxiv.org/abs/2605.27276), [official repo](https://github.com/hexo-ai/sia)

Relevant facts：

- SIA 的 Feedback-Agent 在同一 loop 中选择 harness update 或 weight update。
- 它把 scaffold/harness updates 与 LoRA weight updates 结合，报告在 LawBench、GPU kernel optimization、single-cell RNA denoising 上超过 scaffold-only。
- 论文强调 harness updates 改善搜索和行动方式，weight updates 学到 prompt/scaffold 难以注入的 domain intuition。

Borrow：

- harness + weights 同时更新的 outer-loop framing；
- structured execution trajectory；
- LoRA adapter 作为 weight update unit；
- feedback agent 需要根据 failure mode 决定 update type。

Must add：

- `K_spec` quarantine；
- no-specific-harness evaluation；
- counterfactual rule swap；
- artifact-scrubbed training arm；
- raw SFT as control only。

Our delta：

- SIA 问“两类旋钮一起调是否更强”；我们问“什么经验有资格进 weights，什么经验必须被隔离”。如果不做 quarantine 和 no-specific-harness eval，会和 SIA 的 novelty 混在一起。

## Harness-Bench

Source: [Harness-Bench: Measuring Harness Effects across Models in Realistic Agent Workflows](https://arxiv.org/abs/2605.27922), [project site](https://www.harness-bench.ai/)

Relevant facts：

- Harness-Bench 把 capability 报告在 model-harness configuration level，而不是只归因到 base model。
- 它固定任务环境、budgets、evaluation protocol，同时比较不同 model backend 和 harness configuration。
- 每次 run 保存 final artifacts、execution traces、usage stats、validator outputs。
- 指标不止 completion，也关注 process quality、efficiency、failure behavior。

Borrow：

- run artifact schema；
- process metrics；
- model-harness pair as reporting unit；
- validator output 必须进入 trace。

Mapping to MiniAPI：

- completion：workflow 是否完成；
- security / permission：是否调用 forbidden action；
- robustness：错误码后是否 recover；
- tool use：是否用最小必要 probe；
- consistency：是否和已发现 contract 保持一致；
- cost：token、tool calls、verifier calls。

## AppWorld

Source: [AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents](https://arxiv.org/abs/2407.18901)

Relevant facts：

- AppWorld 有 9 个 daily apps、457 APIs、约 100 个虚拟用户、750 个 agent tasks。
- 评测使用 state-based unit tests，允许多种完成方式，同时检查 collateral damage。

Use：

- MiniAPI 之后的外部验证。
- 检验 contract discovery / safe action ordering 是否能迁移到真实-ish API workflow。

Do not use for v0：

- API 面太大，变量太多，不适合 debug trace abstraction 或 adoption causality。

## tau-bench

Source: [tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://arxiv.org/abs/2406.12045)

Relevant facts：

- tau-bench 模拟 user-agent 对话，agent 有 domain-specific API tools 和 policy guidelines。
- 评测比较最终 database state 与目标 state。
- pass^k 衡量多次试验一致性。

Use：

- MiniAPI 之后验证 policy-following、tool-use consistency、multi-turn reliability。
- 把 pass^k 作为训练后稳定性指标，而不只看 pass@1。

## Terminal-Bench 2

Source: [Terminal-Bench paper PDF](https://openreview.net/pdf/574281303882f822808ab57ac3a57a2bddfbc7a3.pdf), [tbench.ai](https://www.tbench.ai/)

Relevant facts：

- Terminal-Bench 2.0 包含 89 个 hard CLI tasks。
- 每个 task 有独立 container environment、instruction、tests、human-written reference solution、time limit。
- 论文报告 frontier models / agents 在该 benchmark 上低于 65%。

Use：

- secondary validation，尤其是后期证明 harness/skill policy 是否能跨到 command-line agent tasks。

Do not use for v0：

- 失败可能来自 domain gap、terminal harness、base model、环境依赖或 task difficulty，不适合验证最核心的 experience allocation。

## verl

Source: [verl docs](https://verl.readthedocs.io/en/latest/index.html), [Agentic RL Training](https://verl.readthedocs.io/en/latest/start/agentic_rl.html), [GRPO](https://verl.readthedocs.io/en/latest/algo/grpo.html), [LoRA support](https://verl.readthedocs.io/en/latest/advance/ppo_lora.html)

Relevant facts：

- verl 支持 SFT trainer config、PPO/GRPO 等 post-training algorithms。
- Agentic RL 文档支持 async rollout、multi-turn conversations、tool calls、agent loop。
- GRPO 不训练 critic，用 grouped rollouts 和 relative rewards。
- verl 支持 RL algorithms with LoRA；文档给出 8 GPU 级别的大模型 LoRA 参考配置。

Use：

- 服务器阶段统一承载 GRPO / agentic RL。
- SFT 数据也导出成 verl 可读 parquet，使 SFT 和 RL 共享 split、manifest、scrubbing contract。

Constraint：

- verl 之前必须先有 stable verifier reward 和 scrubbed trajectory dataset；否则只是把 leakage 放大进 weights。

# 论文实验规划：Quarantined Skill Adoption

## 文档分工

本文件是唯一的 paper-facing 实验主计划，包含 research questions、实验协议、指标、kill conditions 和 daily checkpoint。不要在别处再维护一份平行日程。

- [docs/MODEL_AND_ENV_REVISIONS.md](MODEL_AND_ENV_REVISIONS.md)：只记录模型路由、API quirks、环境修改原则和可复用命令。
- [docs/result/](result/)：只放 daily factual results、run artifacts、表格和当日解释。
- [docs/RELATED_EXPERIMENTS.md](RELATED_EXPERIMENTS.md)：只放外部工作和可借鉴 protocol。
- [docs/KGEN_INTERACTIVE_PROTOCOL.md](KGEN_INTERACTIVE_PROTOCOL.md)：定义 `k_gen_interactive`、action trace、robust adoption gate。

## 目标

不要先证明完整 co-evolve 大系统，而是用便宜、可控、可验证的 API-only 环境回答三个问题：

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
| `k_gen_exec` | harness 预先给 bounded diagnostic probes | 测可执行证据 scaffold 是否强于 prose |
| `k_gen_interactive` | 模型在预算内执行 hypothesis/query/verify/repair/audit | 测 general learning procedure 是否能降低 learning cost |
| `k_spec_k_gen` | 两者都给 | 测 scaffold 上限 |

指标：

- success / parse accuracy / generation accuracy
- token usage / query calls / verifier calls / repair count / final attempts
- task-level failure cases
- direct target query violations

Kill conditions：

- `k_spec` 不显著强于 `no_scaffold`：任务或 prompt 设计失败。
- `k_gen` 没有 learning-cost 收益：playbook 太空，模型用不上。
- `k_gen_interactive` 接近 `k_spec` 且 query/verifier 证据过宽：protocol 泄漏了 K_spec。
- `k_gen_interactive` 不强于 `k_gen_exec`：交互动作没有提供真实 repair 机制，或 verifier feedback 太弱。
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

Memory proxy 当前实现的安全 variants：

- `stripped`：prose 版 strategy memory。
- `executable_stripped`：保留 hypothesis/query/verifier/repair/audit action protocol，删除 surface artifacts。
- `artifact_scrubbed`：只保留 abstract reusable policy。
- `artifact_scrubbed_executable`：只保留 action policy、quarantine rule 和 promotion gate。

交互版 trace 额外拆成：

- `raw_action`：保留当前 commands、feedback、final answers，只作 leakage control。
- `action_stripped`：保留 action sequence、reason、feedback category、repair pattern，删除 surface artifacts。
- `artifact_scrubbed_action`：只保留动作类型、stop criteria 和 quarantine policy，用作严格训练候选。

评测：

- seen family
- renamed vocab
- morphology/agreement swap
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
- promotion 使用 robust adoption gate：counterfactual / heldout removal delta 必须在容差内非负；seen-only positive skill 只能归入 ephemeral K_spec。

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

## Daily Checkpoints

原 weekly 路线压缩成 daily checkpoint。每一天都要有可运行 artifact，不允许只写故事。模型/环境命令不在这里重复维护；以 `README.md` 和 `docs/MODEL_AND_ENV_REVISIONS.md` 为准。

| Day | 目标 | Done when | 当前状态 |
| --- | --- | --- | --- |
| Day 1 | MiniLang scaffold headroom | generator/verifier 可重复；`run_headroom` 能跑四个 scaffold 条件；hard-mode DeepSeek 至少 8 episode；保存 JSONL records 和 summary | 已完成；见 [docs/result/DAY1_RESULT.md](result/DAY1_RESULT.md) |
| Day 2 | Counterfactual leakage eval | `run_leakage` 比较 source raw rulebook vs target scaffold；覆盖 `renamed_vocab` 和 `order_swap`；生成 parse/generate 分拆表；Qwen route 可用 | 已完成；见 [docs/result/DAY2_LEAKAGE_RESULT.md](result/DAY2_LEAKAGE_RESULT.md) |
| Day 3 | Stronger leakage transforms | 加 `composition_swap`；加入 `heldout_family` split；输出 per-transform parse/generate/token/error table | 已完成；见 [docs/result/DAY3_LEAKAGE_RESULT.md](result/DAY3_LEAKAGE_RESULT.md) |
| Day 4 | Raw / stripped trace dataset | 每个 successful episode 输出 raw、stripped、artifact-scrubbed trace；scrubber 自动拒绝 token mapping、rulebook snippet、答案、family-id | 已完成；见 [docs/result/DAY4_DAY6_API_REPORT.md](result/DAY4_DAY6_API_REPORT.md) |
| Day 5 | API-only distillation proxy | 用 raw / stripped / scrubbed trace 作为 in-context memory；在 seen、renamed、rule_swap、held-out、no-specific-harness 上比较 | 已完成；见 [docs/result/DAY4_DAY6_API_REPORT.md](result/DAY4_DAY6_API_REPORT.md) |
| Day 6 | Offline adoption signal | 构造 useful K_gen、leaking K_spec、description trap、redundant skill library；跑 removal ablation；算 adoption score vs removal delta | 已完成；见 [docs/result/DAY4_DAY6_API_REPORT.md](result/DAY4_DAY6_API_REPORT.md) |
| Day 7 | Executable K_gen repair | `k_gen_exec` 支持 bounded diagnostic probes；summary 记录 query/verifier cost；与 prose `k_gen` 小规模复跑比较 | 已完成；见 [docs/result/KGEN_EXEC_HEADROOM_RESULT.md](result/KGEN_EXEC_HEADROOM_RESULT.md) |
| Day 8 | Interactive K_gen | `k_gen_interactive` 支持 bounded hypothesis/query/verify/repair/audit；records 保存 action trace、query/verifier/repair/final-attempt cost；与 `k_gen_exec` 和 `k_spec` 复跑 headroom | 8-episode headroom 已完成；lean repair 有效但较贵，见 [docs/result/DAY8_INTERACTIVE_KGEN_SMOKE.md](result/DAY8_INTERACTIVE_KGEN_SMOKE.md) |
| Day 9 | Action trace proxy + robust adoption | memory proxy 增加 `raw_action`、`action_stripped`、`artifact_scrubbed_action`；adoption report 同时报 naive adoption 和 robust classification | 2-episode smoke 已完成；safe memory 尚未迁移，robust adoption 已 quarantine source rulebook，见 [docs/result/DAY8_INTERACTIVE_KGEN_SMOKE.md](result/DAY8_INTERACTIVE_KGEN_SMOKE.md) |
| Day 10 | MiniAPI v0 | 500 行以内 simulator；支持 hidden API constraints 和 deterministic verifier；复用 headroom / leakage / adoption 三套协议 | 待做 |
| Day 11 | First paper-facing result pack | 一张 scaffold headroom 表；一张 leakage transform 表；一张 adoption-vs-removal 图或表；一页 kill-condition 结论 | 待做 |

MiniLang server phase gate：只有 Day 3-9 通过后，才考虑上 8xA100 做 MiniLang SFT / GRPO。MiniAPI 是后续 agentic validation，不是启动 MiniLang training 的前置条件。训练细节和 verl / SFT 配置放在 [docs/TRAINING_PLAN.md](TRAINING_PLAN.md)；本文件只保留进入训练的 scientific gate。

训练前必须满足：

1. Stripped trace dataset 通过 leakage scan。
2. Offline adoption 有 removal correlation，并且 robust adoption 不会 promotion K_spec。
3. Eval splits 固定且 manifest 可复现。
4. SFT / verl configs 只消费 scrubbed manifest。

## Later Validation

外部验证顺序：

1. MiniLang family A -> MiniLang family B
2. MiniLang -> MiniAPI
3. MiniAPI -> AppWorld / tau-bench
4. Terminal-Bench 2 only as secondary validation

Hanabi -> Terminal-Bench 2 只适合后期 headline transfer，不适合 v0。

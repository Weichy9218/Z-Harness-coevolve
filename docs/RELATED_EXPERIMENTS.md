# 可借鉴实验和代码

## SAGE

借 sequential rollout、skill library baseline、skill-integrated reward。不要照抄主 claim；我们的主指标是 remove K_spec 后是否仍然变强，以及 adoption score 是否预测 causal usefulness。

## Meta-Harness

借 trace filesystem、source/scores/trajectories 全量记录、proposer 基于历史失败机制改 harness。v0 不先跑 Terminal-Bench 2，只借工程记录方式。

## SIA

借 harness + LoRA 同时更新的 framing。差异必须是 K_spec quarantine、no-specific-harness evaluation、counterfactual rule swap、artifact-scrubbed arm。

## Harness-Bench

借过程指标：completion、robustness、tool use、consistency、token usage、turns、validator output。

## AppWorld / tau-bench

作为 MiniAPI 外部验证，不作为第一天环境。它们适合验证 contract discovery，但变量太多，不适合 debug measurement protocol。

## Terminal-Bench 2

只做 secondary validation。失败归因太难，不适合 v0。


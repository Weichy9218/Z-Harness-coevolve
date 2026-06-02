# 04 下一步计划

## 总结

当前不要训练，也不要直接进入 10-task dev ablation。

H2e 已经完成：reward `0.0`，无 infra exception，但 verifier 缺
`/app/solution.txt`。这不是 H2c/H2d 那种 processor false positive invalid run；
它是一次有效 gate failure。结论是：H2 的 guard 机制变干净了，但还不足以让
`crack-7z-hash` 成功。

H3 failure-mechanism patch 已经完成并在 HarnessX 本地提交：

```text
61977b7 Add TB2 H3 failure-mechanism guards
```

H3 初次 run 是 invalid diagnostic：oh_runs `task_end` 有 `APIConnectionError`，
且 BuildInstallLoopGuard 暴露 false positive。该 false positive 已用 regression
test 修复。

H3b 修复后 real gate 已完成：reward `0.0`，无 infra exception，agent
`exit_reason=budget_exceeded`，verifier 仍缺 `/app/solution.txt`。H3b 是 clean
failure with new mechanism，但不是 pass signal，也不足以进入 dev ablation。

## H0/H1/H2a/H2b/H2c/H2d/H2e 分别是什么

| 名称 | 任务 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| H0 | baseline HarnessX TB2 harness 跑 `crack-7z-hash` | 建立 M0 baseline failure，定位失败机制 | completed，reward `0.0` |
| H1a | prompt-only apt recovery | 测只改 prompt 能否解决 stale apt / install recovery | invalid stopped |
| H1b | strict apt install recovery processor | 只允许 real stale install failure 后做一次 `apt-get update` | diagnostic partial |
| H2a | 第一版 tool-cost + brute-force guard | 阻止 heavy install 重复 timeout 和 unbounded brute force | invalid，暴露 false negative |
| H2b | 修复 H2a 后再跑 | 允许 bounded probe，同时阻止 unbounded wordlist loop | invalid，暴露 false positive |
| H2c | 修复 H2a/H2b 后的 real gate | 判断 H2 是否机制干净，能否进入 dev ablation | invalid，暴露 literal probe false positive |
| H2d | 修复 H2c 后的 real gate | 判断 H2 是否机制干净，能否进入 dev ablation | invalid，暴露 hash-string false positive |
| H2e | 修复 H2d 后的 real gate | 判断 H2 是否机制干净，能否进入 dev ablation | completed，reward `0.0` |
| H3 | failure-mechanism patch 初次 gate | 限制 repeated bounded probe/build loop/final output missing | invalid completed，暴露 BuildInstallLoopGuard false positive + APIConnectionError |
| H3b | H3 false-positive 修复后 gate | 判断 H3 是否能让 `crack-7z-hash` 形成 pass 或 clean failure | completed，reward `0.0`，clean budget failure |

关键解释：

- H0 是有效失败，不是坏事；它给出了 artifact-backed baseline。
- H1a/H2a/H2b/H2c/H2d/H3 是 invalid diagnostic，不是最终失败。
- H1b 证明 apt recovery 方向有用，但不够。
- H2e 是有效 gate failure：它可以进入内部结果整理，但不能支持训练或 dev ablation。
- H3b 是有效 gate failure：H3 processors 干净触发，但仍没有解决任务。

## H2e 为什么没有成功

H2e artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h2e-external-command-regex-crack-gate-20260602
```

结果：

- reward `0.0`；
- infra exceptions `0`；
- verifier 失败原因：`/app/solution.txt` missing；
- runtime `30m 41s`；
- observed Bash calls `95`；
- synthetic tool blocks `7`；
- `AptInstallRecoveryProcessor` 触发 `2` 次；
- `ToolTimeoutStrategyProcessor` 触发 `3` 次；
- `SlowBruteforceGuardProcessor` 触发 `5` 次。

解释：

- H2e 没有复现 H2c/H2d 的误杀问题，所以它不是 invalid。
- H2e 仍大量消耗步骤和 token，说明“允许 bounded probe + 阻止 unbounded brute force”
  还不够。
- 模型仍会在 build `john`、小规模 `7z` probe、工具安装/恢复之间反复尝试，最后没有
  形成正确可验证答案。

## H2e 复现命令

`TB2_API_KEY` 来自 Z repo `.env` 里的 `apihy_API_KEY_deepseek`。

```bash
set -a
source /Users/weichy/code/Z-Harness-coevolve/.env
set +a

PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
TB2_MODEL=deepseek-v3.2 \
TB2_API_BASE=https://zgc.apihy.com/v1 \
TB2_API_KEY="$apihy_API_KEY_deepseek" \
bash /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  -t crack-7z-hash \
  --job-name tb2-1-h2e-external-command-regex-crack-gate-20260602 \
  -n 1 \
  --max-steps 100 \
  --request-timeout-sec 600
```

## H3 建议

H3 的目标不是“提示答案”，而是进一步约束无效工作流。当前已实现：

1. 限制重复 bounded password probe：允许一次小 probe，但多次失败后必须切换策略或停止。
2. 限制 repeated build/install loop：`john/hashcat` build 或 install 超时后，不能反复换目录重试。
3. 增强 self-verify：如果最终没有 `/app/solution.txt`，在最后预算前必须写出候选或明确失败。
4. 给 processor 加 regression tests，确保 H2c/H2d 修过的 false positive 不回归。

H3b single-task gate 结果：

- reward `0.0`；
- no infra exception；
- agent `budget_exceeded` at 100 steps；
- verifier 缺 `/app/solution.txt`；
- `FinalOutputSelfVerifyProcessor` 在 step 90 触发；
- `RepeatedBoundedProbeGuardProcessor` 和 `BuildInstallLoopGuardProcessor` 都有 clean trigger。

所以 H3b 不能进入 10-task same-split dev ablation。下一步应该是 H4/H3c 级别的
post-guard strategy patch，或者把 `crack-7z-hash` 暂时作为 failure-taxonomy case
搁置，先选择另一个 gate task 验证 H3 是否有 transfer value。

## 训练前还需要做什么

训练前有四个 gate。任何一个没过，都不要 SFT / LoRA / GRPO。

| Gate | 谁决定 | 自动检查 | 人工检查 | 当前状态 |
| --- | --- | --- | --- | --- |
| G1: H* 合法 | 人工预注册标准 | processor tests、verifier/test leakage scan | 确认没有 task-specific answer 或 benchmark shortcut | 未完成 |
| G2: H* 有效 | 自动 run + 人工复核 | H0/M0 vs H*/M0 same-split dev ablation | 确认收益不是 infra noise 或过拟合单 task | 未完成 |
| G3: train 数据可用 | 自动 export + 人工抽查 | 只导出 train split、reward `1.0`、accepted trajectories | 抽查轨迹无泄漏、无错误策略 | 未完成 |
| G4: heldout 隔离 | 自动 manifest check | heldout/test never exported | 确认没有根据 heldout 改 H* 或调训练 | 未完成 |

更具体地说，训练前要补完这些内容：

1. 固化 H3 candidate。
   - 已在 HarnessX commit `61977b7` 实现 repeated bounded probe guard。
   - 已实现 repeated build/install loop guard，并修复已 blocked tool call 被误计的 false positive。
   - 已强化 final self-verification：预算快结束且没有 `/app/solution.txt` 时触发 hard reminder。
   - HarnessX targeted tests 当前 `32 passed`。

2. 跑 H3 single-task gate。
   - 已跑 H3 初次 gate：invalid diagnostic。
   - 已跑 H3b 修复后 gate：completed，reward `0.0`，clean failure。
   - H3b failure mechanism 和 H0/H2e 不同，但仍是 100-step budget exhaustion，
     扩跑价值不足，不建议直接 dev ablation。

3. 跑 10-task same-split dev ablation。
   - H0/M0：baseline harness。
   - H*/M0：candidate harness。
   - 同一 dev split、同一模型路由、同一 budget。
   - 至少要看到 H*/M0 多 1 个 pass，且没有不可解释的 H0 pass -> H* fail。
   - 当前状态：不要跑。H3b 没有 single-task pass，也没有足够的 cost/behavior 改善信号。

4. 冻结 H*。
   - 记录 HarnessX commit 或完整 patch diff。
   - 记录 Z repo ledger、split manifest、summary script version。
   - H* 冻结后不能再根据 dev 结果改 policy。

5. 建立真实 train split。
   - 现在 train split 为空，这是正确的。
   - H* 冻结后再用 fresh metadata 生成 train split。
   - dev tuning 和 heldout/test 不能进入 train。

6. 用冻结 H* 采 train trajectories。
   - 只收 train split。
   - 只收 completed、reward `1.0`、无 infra exception 的 trajectories。
   - 失败轨迹只能用于 taxonomy，不能进 SFT candidates。

7. 做 sanitizer / leakage scan / sampled review。
   - 删除或屏蔽 API key、路径里不该训练的本地信息、verifier/test 内容。
   - 排除 dev、heldout、invalid、failed trajectories。
   - 人工抽查一小批，确认 agent 学到的是通用 tool-use behavior，不是答案记忆。

8. 生成训练 artifact。
   - `sft_candidates.jsonl` 只能来自 accepted train successes。
   - 每条样本保留 task id、harness variant、reward、artifact root、sanitizer status。
   - 训练配置里记录 base model、LoRA/optimizer、dataset hash、split hash。

9. 训练后做 heldout / tau-bench transfer。
   - TB2 heldout 只做最终评估。
   - tau-bench / tau3-bench 用来检查 transfer，不参与 H* 选择。
   - 如果 heldout/tau 失败，只能回到新一轮 protocol，不能把 heldout 轨迹补进训练。

## dev ablation 条件

只有 H3 或后续 gate clean 且有合理收益信号后才跑：

1. H0/M0 dev split：从 pinned H0 HarnessX commit 或 clean H0 worktree 跑。
2. H*/M0 dev split：从当前 H* HarnessX worktree 跑。
3. 两边固定 model route、API base、sandbox、dev split、max steps、request timeout、concurrency。

成功标准：

- H*/M0 在 10-task dev split 上比 H0/M0 至少多 1 个 pass；
- 没有不可解释的 H0 pass -> H* fail regression；
- infra errors 不增加；
- token/runtime/tool-call overhead 不超过 guardrail，除非有明确 pass gain。

## dev ablation 后

如果 H*/M0 成功：

1. 冻结 H*；
2. 记录 HarnessX exact commit 或 patch diff；
3. 验证 dev split task metadata；
4. 建立真实 train split，排除 dev tuning 和 heldout；
5. 只收 accepted H* train trajectories；
6. export sanitized SFT candidates；
7. 做 leakage scan 和 sampled human review；
8. 再准备 Qwen 8B SFT / LoRA；
9. tau-bench 作为 transfer check。

如果 H*/M0 失败：

1. 不训练；
2. 回到 failure taxonomy；
3. 判断是 H3 policy 无效、task cluster 太窄、还是 runtime/env 问题；
4. 设计 H4/H3c，或回滚到 H1b/H2e/H0 作为对照。

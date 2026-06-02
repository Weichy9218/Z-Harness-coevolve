# 03 数据集与结果整理

## Terminal-Bench 2.1

当前主 benchmark：

- dataset: `terminal-bench/terminal-bench-2-1`
- runner: HarnessX local Docker
- sandbox: `DinDDockerEnvironment`, `network_mode=host`
- fixed model: `deepseek-v3.2`
- API base: `https://zgc.apihy.com/v1`

split manifest：

```text
splits/terminal_bench_2_1/harness_only_v0_manifest.json
splits/terminal_bench_2_1/harness_dev_v0.tasks.json
splits/terminal_bench_2_1/harness_train_v0.tasks.json
splits/terminal_bench_2_1/harness_heldout_v0.tasks.json
```

注意：dev split 目前仍需用 fresh Harbor metadata 再验证一次。train split 当前为空，
这是设计选择：H* 冻结前不能收训练轨迹。

## Qwen Route Diagnostics

当前先排除 `boyue_base_url` 上的 `qwen3-8b` route，不把它用于 TB2 metric：

- `boyue_base_url` + `boyue_apikey` 能列出并调用 `qwen3-8b`，且
  `extra_body={"enable_thinking": false}` 生效；
- 但同一个 TB2 first tool-calling request 出现严重 tail latency 和重复 502：
  有时 1-2 秒返回，有时 60-120 秒，甚至超过 3 分钟无响应；
- diagnostic job
  `tb2-qwen3-8b-thinking-off-crack-gate-20260602-222936` 在 step 0
  没有任何 assistant/tool response，oh_runs `task_end` 是
  `InternalServerError: Error code: 502`，`total_tokens=0`；
- 因此该 route 暂时标记为 `excluded_for_now`，后续除非重新通过 route smoke，
  否则不能作为 Qwen 8B benchmark metric。

`apihy_BASE_URL=https://zgc.apihy.com/v1` + `apihy_API_KEY_qwen` 不能替代
8B route：模型列表没有 `qwen3-8b`，直接请求 `qwen3-8b` / `Qwen/Qwen3-8B`
返回 `model_not_found` / 无可用渠道。该 route 上的 `qwen3-14b` 和 `qwen3-32b`
first tool-calling smoke 正常；其中 `qwen3-14b` 的 1-step HarnessX smoke
`tb2-apihy-qwen3-14b-thinking-off-smoke-20260602-224531` 无 exception，但它超过
`<=8B` 约束，只能用于 runner/client 通路验证，不能作为 8B student track metric。

后续 Qwen3-8B route 改为服务器 `tyyun_galaxy_1` 上的 vLLM deployment，而不是
复用上述不稳定或不满足约束的第三方 route。新 route 跑出的结果必须单独标记为
Qwen3-8B/vLLM/server track，不能和历史 `deepseek-v3.2` H0-H4e 结果直接混成
同一 metric。后续 gate 默认 `MAX_STEPS=50`；历史 H0-H4e 的 100-step 结果仅作为
failure taxonomy 和对照证据保留。

改 harness 的 meta-agent 可以使用
`GPT_sub2api_URL=https://ie-crs.haoxiang.ai/v1` 上的 `gpt5.5`。它只用于
architecture/code/docs 工作，不进入 Terminal-Bench task-agent trajectory。

## 本地 Terminal-Bench 尝试总表

这张表是当前本地已经做过的 TB2.1 `crack-7z-hash` 尝试记录。它的用途是把
“实验失败”“invalid diagnostic”“有效 gate failure”分开，避免把调 harness
过程中的中间 run 当成最终结果。

| 阶段 | job | 状态 | reward | 是否可作为 metric | 主要发现 |
| --- | --- | --- | --- | --- | --- |
| H0 | `tb2-1-h0-smoke` | completed | `0.0` | yes, baseline | baseline harness 会进入 tool/runtime failure loop，最终缺 `/app/solution.txt` |
| H1a | `tb2-1-h1-apt-recovery-crack-gate-20260602` | invalid stopped | n/a | no | prompt-only 不干净，仍有 preemptive `apt-get update` 和 slow brute-force drift |
| H1b | `tb2-1-h1b-strict-apt-gate-crack-20260602` | invalid stopped / diagnostic | n/a | no | strict apt recovery 有效，但 heavy install timeout 和 slow brute force 仍在 |
| H2a | `tb2-1-h2-tool-cost-crack-gate-20260602` | invalid stopped | n/a | no | first guard 没挡住 unbounded loop，false negative |
| H2b | `tb2-1-h2b-tool-cost-crack-gate-20260602` | invalid stopped | n/a | no | guard 错挡小规模 literal probe，false positive |
| H2c | `tb2-1-h2c-tool-cost-crack-gate-20260602` | invalid stopped | n/a | no | `cat` 在成功分支中被误判为 wordlist source，false positive |
| H2d | `tb2-1-h2d-literal-probe-crack-gate-20260602` | invalid stopped | n/a | no | `$7z$` hash string 被误判为外部 `7z` 命令，false positive |
| H2e | `tb2-1-h2e-external-command-regex-crack-gate-20260602` | completed | `0.0` | yes, gate failure | no infra exception，但仍没有写 `/app/solution.txt`；H2 clean 但不足 |
| H3 | `tb2-1-h3-failure-mechanism-crack-gate-20260602` | invalid completed / diagnostic | `0.0` | no | pre-fix H3 run：oh_runs `task_end` 有 `APIConnectionError`，且 BuildInstallLoopGuard 把已 blocked apt command 误计为 install failure |
| H3b | `tb2-1-h3b-failure-mechanism-crack-gate-20260602` | completed | `0.0` | yes, gate failure | H3 guards 干净触发，但 agent `budget_exceeded`，verifier 仍缺 `/app/solution.txt` |
| H4 | `tb2-1-h4-post-guard-contract-crack-gate-20260602-211811` | invalid cancelled / diagnostic | n/a | no | pre-fix H4 run：CostlyCrackingGuard 把 `/app/john/...` discovery path 误判为 `john` cracking executable；随后 verifier 阶段被 caller timeout 取消 |
| H4d | `tb2-1-h4d-post-guard-contract-crack-gate-20260602-215110` | invalid completed / diagnostic | `0.0` | no | H4 false positive 修复后 rerun；Harbor completed，但 oh_runs `task_end` 是 `APIConnectionError`，verifier 仍缺 `/app/solution.txt` |
| H4e | `tb2-1-h4e-clean-rerun-crack-gate-20260602-221736` | completed | `0.0` | yes, gate failure | clean H4 rerun：agent `budget_exceeded` at 100 steps，verifier 仍缺 `/app/solution.txt`；无 pass/收益信号 |

当前只有 H0、H2e、H3b、H4e 能作为内部 gate/baseline 结果比较。H1a/H1b/H2a/H2b/H2c/H2d/H3/H4/H4d
是 harness debugging 证据，只能用于 failure taxonomy 和 regression tests。

## H0 Baseline Result

H0 smoke artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke
```

| 字段 | 值 |
| --- | --- |
| task | `terminal-bench/crack-7z-hash` |
| reward | `0.0` |
| verifier failure | missing `/app/solution.txt` |
| observed Bash calls | `93` |
| reported input tokens | `1448375` |
| infra errors | `0` |

结论：H0 是有效 baseline failure。失败不是“TB2 坏了”，而是 harness/runtime
strategy 暴露问题：

- bundled `john` binary 需要 AVX2；
- `hashcat` install 遇到 stale apt metadata / 404；
- H0 prompt 让模型避免 `apt-get update`；
- 模型 drift 到慢速 per-password `7z` brute force；
- 最终超预算且没有写 `/app/solution.txt`。

## H1/H2 Gate 结果

| 阶段 | 状态 | 结论 |
| --- | --- | --- |
| H1a prompt-only | invalid stopped | 不是干净机制，模型仍 preemptive `apt-get update` 并 drift |
| H1b strict apt recovery | diagnostic partial | apt recovery 生效，但 heavy install timeout 和 slow brute force 仍在 |
| H2a first tool-cost guard | invalid stopped | false negative：guard 没挡住 unbounded loop |
| H2b bounded probe fix | invalid stopped | false positive：guard 错挡小规模 literal password probe |
| H2c | invalid stopped | step 29 小 literal probe 被 `cat` 误判为 wordlist source，false positive |
| H2d | invalid stopped | hash parser 中的 `$7z$` 字符串被误判为外部 `7z` 命令，false positive |
| H2e | completed，reward `0.0` | clean completed gate：无 infra exception，但没有写 `/app/solution.txt` |

H2a/H2b/H2c/H2d 不算最终失败，也不能写进 paper metric。它们的作用是暴露
processor policy bug，并促成 regression tests。

H2e 是有效 gate failure，可以写进内部结果 ledger，但还不能证明 H2 有 dev-scale
收益。它的含义是：apt recovery、tool timeout、slow brute-force guard 已经能介入
主要 failure loop，但当前 H2 policy 仍不足以把 `crack-7z-hash` 做成。

H2e artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h2e-external-command-regex-crack-gate-20260602
```

H2e summary：

```text
artifacts/tb2_1_harness_only/h2e_summary.json
```

| 字段 | 值 |
| --- | --- |
| task | `terminal-bench/crack-7z-hash` |
| trial | `crack-7z-hash__EY23G3b` |
| reward | `0.0` |
| infra exceptions | `0` |
| verifier failure | missing `/app/solution.txt` |
| runtime | `30m 41s` |
| observed assistant steps | `96` |
| observed Bash calls | `95` |
| job input tokens | `1408214` |
| raw output tokens from oh_runs | `12153` |
| synthetic tool blocks | `7` |

H2e processor triggers：

| processor | count |
| --- | --- |
| `AptInstallRecoveryProcessor` | `2` |
| `ToolTimeoutStrategyProcessor` | `3` |
| `SlowBruteforceGuardProcessor` | `5` |
| `CustomSelfVerifyProcessor` | `3` |
| `CompactionProcessor` | `2` |
| `PostCompactionRefreshProcessor` | `2` |

## H3 Gate 结果

H3 patch 目标仍是通用 harness policy，不提示答案：

- 限制 repeated bounded password probe；
- 限制 repeated build/install loop；
- 强化 final self-verification：step budget 接近结束且 task description 要求
  `/app/solution.txt` 时检查文件是否存在且非空；
- 保留 H2c/H2d false-positive regression tests。

HarnessX 当前 H3 commit：

```text
61977b7 Add TB2 H3 failure-mechanism guards
```

H3 初次 artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h3-failure-mechanism-crack-gate-20260602
```

H3 初次 run 不作为 metric。虽然 Harbor top-level 是 completed、reward `0.0`、
`exception_info=null`，但 oh_runs 的 `task_end` 是 `exit_reason=error`，
`error=APIConnectionError: Connection error.`；同时 BuildInstallLoopGuard 将一个
已被 AptInstallRecovery blocked 的 synthetic apt command 误计为 install failure。
这个 false positive 已由 regression test 修复。

H3b artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h3b-failure-mechanism-crack-gate-20260602
```

H3b summary：

```text
artifacts/tb2_1_harness_only/h3b_summary.json
```

| 字段 | 值 |
| --- | --- |
| task | `terminal-bench/crack-7z-hash` |
| trial | `crack-7z-hash__nTdefcg` |
| reward | `0.0` |
| infra exceptions | `0` |
| agent exit reason | `budget_exceeded` |
| verifier failure | missing `/app/solution.txt` |
| runtime | `29m 33s` |
| observed assistant steps | `100` |
| observed Bash calls | `100` |
| job input tokens | `1712622` |
| raw output tokens from oh_runs | `14773` |
| synthetic tool blocks | `12` |

H3b processor triggers：

| processor | count |
| --- | --- |
| `AptInstallRecoveryProcessor` | `2` |
| `BuildInstallLoopGuardProcessor` | `5` |
| `CompactionProcessor` | `3` |
| `EnvironmentContextInjector` | `1` |
| `FinalOutputSelfVerifyProcessor` | `1` |
| `PostCompactionRefreshProcessor` | `3` |
| `RepeatedBoundedProbeGuardProcessor` | `1` |
| `SlowBruteforceGuardProcessor` | `8` |
| `SystemPromptProcessor` | `1` |

H3b 是 clean failure with new mechanism：

- H3 修复后的 BuildInstallLoopGuard 不再误计已 blocked tool call。
- RepeatedBoundedProbeGuard 在一次 bounded probe 后阻断继续换小列表 probe。
- FinalOutputSelfVerify 在 step 90 触发，但模型仍没有写出 verified
  `/app/solution.txt`。
- 模型后期转向 hashcat 和小规模 mask/wordlist 尝试，但仍没有 recover password，
  最终耗尽 100 steps。

结论：H3b 不能支持训练，也不足以直接进入 10-task dev ablation。下一步应先分析
post-guard strategy deadlock，决定是否做 H4/H3c，或者把 `crack-7z-hash` 暂时
降级为 failure-taxonomy case。

## H4 Gate 结果

H4 patch 目标仍是通用 harness policy，不提示答案：

- 新增 `CostlyCrackingGuardProcessor`：对 approved `hashcat` / executable `john`
  cracking attempts 记录 exhausted、no-recovery、timeout 等 no-progress evidence；
- 默认允许一次 bounded proof 和一次 serious attempt，同一 cracking family 积累两次
  no-progress evidence 后阻断继续扩大 wordlist、mask 或 timeout；
- discovery / format diagnosis / result inspection 继续允许，例如 `--help`、`--version`、
  `--example-hashes`、`--show`、`--status`、hash parser、路径/文件检查；
- `FinalOutputSelfVerifyProcessor` 默认从 step budget `0.75` 触发，而不是 `0.90`。

H4 初次 artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h4-post-guard-contract-crack-gate-20260602-211811
```

H4 初次 run 不作为 metric。它暴露了 CostlyCrackingGuard false positive：`/app/john/...`
目录、`7z2john.pl` 脚本、`/app/john/src` build/discovery path 被误判为 `john`
cracking executable。这个问题已用 focused regression tests 修复。

H4d artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h4d-post-guard-contract-crack-gate-20260602-215110
```

H4d summary：

```text
artifacts/tb2_1_harness_only/h4d_summary.json
```

| 字段 | 值 |
| --- | --- |
| task | `terminal-bench/crack-7z-hash` |
| trial | `crack-7z-hash__LLfmdhR` |
| Harbor reward | `0.0` |
| Harbor infra exceptions | `0` |
| oh_runs exit reason | `error` |
| oh_runs error | `APIConnectionError: Connection error.` |
| verifier failure | missing `/app/solution.txt` |
| runtime | `17m 55s` |
| observed assistant steps | `64` |
| observed Bash calls | `64` |
| job input tokens | `741325` |
| synthetic tool blocks | `9` |

H4d processor triggers：

| processor | count |
| --- | --- |
| `AptInstallRecoveryProcessor` | `2` |
| `BuildInstallLoopGuardProcessor` | `5` |
| `CompactionProcessor` | `1` |
| `EnvironmentContextInjector` | `1` |
| `PostCompactionRefreshProcessor` | `1` |
| `RepeatedBoundedProbeGuardProcessor` | `1` |
| `SlowBruteforceGuardProcessor` | `5` |
| `SystemPromptProcessor` | `1` |
| `ToolTimeoutStrategyProcessor` | `1` |

H4d 是 invalid completed diagnostic：Harbor top-level completed 且 `exception_info=null`，
但 oh_runs `task_end` 是 `exit_reason=error` / `APIConnectionError`。因此 H4d 不进入
metric 比较，也不能支持 10-task dev ablation 或训练。

H4e clean rerun artifact：

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h4e-clean-rerun-crack-gate-20260602-221736
```

H4e summary：

```text
artifacts/tb2_1_harness_only/h4e_summary.json
```

| 字段 | 值 |
| --- | --- |
| task | `terminal-bench/crack-7z-hash` |
| trial | `crack-7z-hash__NySEtQ6` |
| reward | `0.0` |
| Harbor exceptions | `0` |
| agent exit reason | `budget_exceeded` |
| verifier failure | missing `/app/solution.txt` |
| runtime | `33m 50s` |
| observed assistant steps | `100` |
| observed Bash calls | `100` |
| job input tokens | `1431031` |
| raw output tokens from oh_runs | `16101` |
| synthetic tool blocks | `8` |

H4e processor triggers：

| processor | count |
| --- | --- |
| `AptInstallRecoveryProcessor` | `2` |
| `BuildInstallLoopGuardProcessor` | `4` |
| `CompactionProcessor` | `3` |
| `EnvironmentContextInjector` | `1` |
| `FinalOutputSelfVerifyProcessor` | `1` |
| `PostCompactionRefreshProcessor` | `3` |
| `RepeatedBoundedProbeGuardProcessor` | `3` |
| `SlowBruteforceGuardProcessor` | `4` |
| `SystemPromptProcessor` | `1` |
| `ToolTimeoutStrategyProcessor` | `2` |

H4e 是 clean completed gate failure：没有 Harbor exception，也没有 oh_runs API error；
但 `FinalOutputSelfVerifyProcessor` 在 step 75 触发后，agent 仍继续跑到 100-step
budget exhaustion，最终没有写 `/app/solution.txt`。这说明 H4 patch 合法性问题已
基本收敛，但没有 pass 或强收益信号。当前不应继续围绕 `crack-7z-hash` 做同题
micro-iteration，也不应进入 10-task dev ablation 或训练。更合理的下一步是把
`crack-7z-hash` 暂时降级为 failure-taxonomy case，换另一个 gate task 验证
H3/H4 是否有 transfer value。

## 本地代码同步状态

Z repo 已记录并同步当前 TB2 文档、ledger 和 export policy。

HarnessX 本地有 Terminal-Bench 相关提交：

```text
4143465 Add TB2 harness-only H2 guards
266e23b Fix TB2 brute-force guard false positives
61977b7 Add TB2 H3 failure-mechanism guards
```

这些提交目前还没有推到 `Darwin-Agent/HarnessX` 远端，因为当前 GitHub 身份对该
仓库没有写权限。它们仍然是当前本地 H2e/H3 继续工作的 runnable substrate。无关的
`recipe/gaia_evolver/data/` 不属于 TB2 主线，本轮忽略。

## 当前测试结果

Z repo：

```text
18 passed
```

HarnessX targeted tests：

```text
41 passed
```

## SFT Export 结果

当前 export：

```text
artifacts/tb2_1_harness_only/sft_candidates.jsonl
```

当前 candidates：

```text
n_candidates = 0
```

这是正确状态。原因：

- H* 尚未冻结；
- train split 为空；
- 没有 accepted successful train trajectories；
- dev tuning / invalid / failed / heldout trajectories 都不能进入训练。

为便于检查同一 task 的多次 harness 行为，另有一个 diagnostic draft export：

```text
artifacts/tb2_1_harness_only/sft_drafts_crack_7z_hash_multiharness.jsonl
artifacts/tb2_1_harness_only/sft_drafts_crack_7z_hash_multiharness.jsonl.manifest.json
```

该文件有 `6` 条 `crack-7z-hash` 多 harness 轨迹，结构兼容
`tb2_sft_candidate_v0` 的 `messages` / `tool_definitions` 字段，但 schema 是
`tb2_sft_draft_v0`，且每条都标记
`training_policy.accepted_for_positive_sft=false`。用途是人工 review、failure
taxonomy 或后续偏好/反例数据设计；不能直接作为正样本 SFT 训练数据。

## tau-bench

tau-bench 目前还没有正式结果。它是 TB2 H* 冻结后的 transfer check。

后续需要单独建立：

- tau split manifest；
- baseline HarnessX run；
- H* transfer run；
- pass^k / final-state success / policy violation / tool cost 指标；
- tau-specific export policy。

## MiniLang 历史结果

MiniLang 结果只作为 archived background 保留，不再驱动当前计划。

有用结论：

- `K_spec` 有明显 headroom，但不能直接蒸馏；
- raw trace 会泄漏；
- prose `K_gen` 太弱；
- executable scaffold 比 prose advice 强；
- naive adoption 可能提升 leaking `K_spec`，必须做 counterfactual / heldout check。

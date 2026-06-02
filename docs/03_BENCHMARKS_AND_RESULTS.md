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

当前只有 H0 和 H2e 能作为内部 gate/baseline 结果比较。H1a/H1b/H2a/H2b/H2c/H2d
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

## 本地代码同步状态

Z repo 已记录并同步当前 TB2 文档、ledger 和 export policy。

HarnessX 本地有 Terminal-Bench 相关提交：

```text
4143465 Add TB2 harness-only H2 guards
266e23b Fix TB2 brute-force guard false positives
```

这两个提交目前还没有推到 `Darwin-Agent/HarnessX` 远端，因为当前 GitHub 身份对该
仓库没有写权限。它们仍然是当前本地 H2e/H3 继续工作的 runnable substrate。无关的
`recipe/gaia_evolver/data/` 不属于 TB2 主线，本轮忽略。

## 当前测试结果

Z repo：

```text
18 passed
```

HarnessX targeted tests：

```text
26 passed
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

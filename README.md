# Z-Harness-coevolve

这个 repo 是 HarnessX benchmark 复现实验的 controller。当前核心不是
MiniLang，也不是直接训练模型，而是：

1. 在 HarnessX 上复现 Terminal-Bench 2.1；
2. 验证 H0/H1/H2 这些 harness-only 改动是否真的有效；
3. TB2 稳定后，再做 tau-bench / tau3-bench transfer；
4. 只有 accepted successful train trajectories 才能进入后续 SFT / LoRA / GRPO。

`zharness/envs/minilang/` 可以保留历史代码和结果，但不再作为当前主线。

## 当前状态

不要训练。

最近 gate 是 Terminal-Bench 2.1 的 H2e：

- substrate: `/Users/weichy/code/HarnessX`
- controller: `/Users/weichy/code/Z-Harness-coevolve`
- benchmark: `terminal-bench/terminal-bench-2-1`
- model: `deepseek-v3.2`
- API base: `https://zgc.apihy.com/v1`
- sandbox: HarnessX local Docker / `DinDDockerEnvironment`, `network_mode=host`

`TB2_API_KEY` 是模型接口 key，来自本 repo `.env` 里的
`apihy_API_KEY_deepseek`。它不是 Terminal-Bench 数据集 key，不能提交。

H2e 已完成：reward `0.0`，无 infra exception，但 verifier 缺
`/app/solution.txt`。它不是 invalid run；它说明 H2 guard 机制已经比 H2c/H2d
干净，但还不足以让 `crack-7z-hash` 成功。当前下一步是 H3 failure-mechanism
patch，而不是直接训练或扩跑 dev ablation。

## 文档结构

docs 只保留 4 个方向：

- [系统架构](docs/01_SYSTEM_ARCHITECTURE.md)：目标、repo 分工、当前方法、运行环境。
- [相关工作](docs/02_RELATED_WORK.md)：SIA、Meta-Harness、Harness-Bench、Terminal-Bench、tau-bench、verl 的关系。
- [数据集与结果](docs/03_BENCHMARKS_AND_RESULTS.md)：benchmark、split、H0/H1/H2 当前结果、export 状态。
- [下一步计划](docs/04_NEXT_PLAN.md)：H0/H1/H2a/H2b/H2c/H2d/H2e 的定义、用途、成功标准和后续路线。

## H2e 复现命令

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

当前进入 dev ablation 的标准：

- H3 或后续 gate 至少给出 clean pass 或明确的收益信号；
- 没有 processor false positive / false negative；
- 再用同一 model route 和同一 split 跑 H0/M0 vs H*/M0。

## 本地检查

Z repo：

```bash
/Users/weichy/code/Z-Harness-coevolve/.venv/bin/python -m pytest -q
```

HarnessX targeted tests：

```bash
PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
/Users/weichy/code/HarnessX/.venv/bin/python -m pytest \
  tests/unit/test_harness_config_hydra.py \
  tests/unit/test_tb2_harness_processors.py \
  -q
```

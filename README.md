# Z-Harness-coevolve

这个 repo 是 HarnessX benchmark 复现实验的 controller。当前核心不是
MiniLang，也不是直接训练模型，而是：

1. 在 HarnessX 上复现 Terminal-Bench 2.1；
2. 验证 H0-H4 这些 harness-only 改动是否真的有效；
3. TB2 稳定后，再做 tau-bench / tau3-bench transfer；
4. 只有 accepted successful train trajectories 才能进入后续 SFT / LoRA / GRPO。

`zharness/envs/minilang/` 可以保留历史代码和结果，但不再作为当前主线。

## 当前状态

不要训练。

最近 gate 是 Terminal-Bench 2.1 的 H4e：

- substrate: `/Users/weichy/code/HarnessX`
- controller: `/Users/weichy/code/Z-Harness-coevolve`
- benchmark: `terminal-bench/terminal-bench-2-1`
- model: `deepseek-v3.2`
- API base: `https://zgc.apihy.com/v1`
- sandbox: HarnessX local Docker / `DinDDockerEnvironment`, `network_mode=host`

`TB2_API_KEY` 是模型接口 key，来自本 repo `.env` 里的
`apihy_API_KEY_deepseek`。它不是 Terminal-Bench 数据集 key，不能提交。

H3b 已完成：reward `0.0`，无 infra exception，但 agent `budget_exceeded`，
verifier 缺 `/app/solution.txt`。它是 clean gate failure，不支持训练或扩跑
dev ablation。

H4 candidate 已实现 costly cracking no-progress ledger 和相关 regression tests。
H4 初次 run 暴露 CostlyCrackingGuard false positive；H4d 被 oh_runs
`APIConnectionError` 污染；H4e 是 clean completed gate failure：Harbor exceptions
`0`，reward `0.0`，agent `budget_exceeded` at 100 steps，verifier 仍缺
`/app/solution.txt`。所以 H4 当前没有 pass 或强收益信号，不能训练，也不要直接
进入 10-task dev ablation。下一步应把 `crack-7z-hash` 暂时降级为
failure-taxonomy case，换一个 gate task 验证 H3/H4 是否有 transfer value。

下一阶段 protocol 已调整：

- 根据 H0-H4e 的经验，优先优化 HarnessX 架构和通用 runtime policy，而不是继续给
  `crack-7z-hash` 追加窄规则；
- 后续 Terminal-Bench gate 默认 `MAX_STEPS=50`；
- 做题模型切换为服务器 `tyyun_galaxy_1` 上 vLLM 部署的 Qwen3-8B；
- 改 harness / 写 processor / 整理文档的 meta-agent 可以使用
  `GPT_sub2api_URL=https://ie-crs.haoxiang.ai/v1` 上的 `gpt5.5`，但它不作为
  Terminal-Bench task-agent metric。

## 文档结构

docs 只保留 4 个方向：

- [系统架构](docs/01_SYSTEM_ARCHITECTURE.md)：目标、repo 分工、当前方法、运行环境。
- [相关工作](docs/02_RELATED_WORK.md)：SIA、Meta-Harness、Harness-Bench、Terminal-Bench、tau-bench、verl 的关系。
- [数据集与结果](docs/03_BENCHMARKS_AND_RESULTS.md)：benchmark、split、H0-H4 当前结果、export 状态。
- [下一步计划](docs/04_NEXT_PLAN.md)：H0-H4 的定义、用途、成功标准和后续路线。

## 下一轮 gate 命令模板

```bash
set -a
source /Users/weichy/code/Z-Harness-coevolve/.env
set +a

PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
TB2_MODEL=qwen3-8b \
TB2_API_BASE=<tyyun_galaxy_1 vLLM OpenAI-compatible /v1 endpoint> \
TB2_API_KEY="<server-local or deployment key>" \
bash /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  -t <new-gate-task> \
  --job-name tb2-qwen3-8b-harness-architecture-gate-YYYYMMDD \
  -n 1 \
  --max-steps 50 \
  --request-timeout-sec 600
```

当前进入 dev ablation 的标准：

- H4 或后续 gate 至少给出 clean pass 或明确的收益信号；
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

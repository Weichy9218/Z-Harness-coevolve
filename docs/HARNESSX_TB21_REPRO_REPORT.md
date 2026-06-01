# HarnessX Terminal-Bench 2.1 Reproduction Report

Date: 2026-06-02

## Executive Summary

本地 HarnessX + Harbor + Docker + Terminal-Bench 2.1 的复现链路已经打通：

```text
terminal-bench/terminal-bench-2-1
-> Harbor local Docker trial
-> HarnessXAgent
-> HarnessX RunLoop + Bash sandbox
-> HarnessJournal oh_runs traces
-> Terminal-Bench verifier
-> Harbor result.json
```

结论分两层：

1. **环境与框架复现成功。** Terminal-Bench 2.1 dataset 能解析，local Docker verifier 能运行，oracle 在 `terminal-bench/crack-7z-hash` 上 reward `1.0`。HarnessXAgent 能进入 RunLoop、调用 Bash tool、写出 `oh_runs` trace，并产出 Harbor result。
2. **当前 H0 agent/harness 没有解出任务。** DeepSeek route + default TB2 HarnessX config 在同一任务上 reward `0.0`，0 exception，运行 31m07s；verifier 失败原因是 `/app/solution.txt` 不存在。失败不是 2.1 接入错误，而是 H0 的 long-horizon control / tool-choice / finish policy 不够强。

因此，下一步不是训练 Qwen 8B，而是先做一个 narrow H1 harness iteration：减少无效工具探索、加强完成态检测、约束长命令/后台任务，并在 2.1 smoke task 上证明 step count 和 failure mode 有改善。

## Environment

- Z-Harness branch: `codex/interactive-kgen-results`
- Z-Harness commit with direction reset: `460a82a`
- HarnessX branch: `codex/tb2-1-adapter`
- HarnessX adapter commit: `76f2421`
- Dataset: `terminal-bench/terminal-bench-2-1`
- Harbor: `0.13.0`
- Docker server: `28.5.2`
- Local HarnessX adapter: `/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2`
- Local job root: `/Users/weichy/code/HarnessX/.benchmarks/tb2`

## Adapter State

The local HarnessX adapter was updated for Terminal-Bench 2.1:

- `DATASET = "terminal-bench/terminal-bench-2-1"`
- `tb2_eval.py` normalizes short task names. Example: `-t crack-7z-hash` becomes `terminal-bench/crack-7z-hash`.
- API key is passed through `api_key_env=TB2_MODEL_API_KEY`, so Harbor artifacts store the env var name rather than the secret value.
- Local Docker no longer forwards loopback host proxies like `127.0.0.1:7897` into verifier containers by default. This fixed the earlier verifier-side `apt/curl/uvx` failure.

## Run 1: Terminal-Bench 2.1 Oracle Smoke

Purpose: prove that the 2.1 dataset, local Docker backend, and verifier are healthy independent of HarnessX policy quality.

Command:

```bash
PATH="/Users/weichy/code/HarnessX/.venv/bin:$PATH" \
  harbor run \
  --dataset terminal-bench/terminal-bench-2-1 \
  --agent oracle \
  --jobs-dir /Users/weichy/code/HarnessX/.benchmarks/tb2 \
  --n-concurrent 1 \
  --include-task-name terminal-bench/crack-7z-hash \
  --environment-import-path benchmarks.terminal_bench_2.dind_environment:DinDDockerEnvironment \
  --ek network_mode=host \
  --no-force-build \
  --no-delete \
  --yes \
  --job-name tb2-1-oracle-env-smoke
```

Result:

- Job path: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-oracle-env-smoke`
- Reward: `1.0`
- Exceptions: `0`
- Runtime: `52s`

Interpretation:

- Terminal-Bench 2.1 package resolution works.
- Local Docker + verifier works.
- The task itself is solvable under this local setup.

## Run 2: Terminal-Bench 2.1 HarnessX H0 Smoke

Purpose: test the current default HarnessX terminal agent path on the same task.

Command:

```bash
set -a; source /Users/weichy/code/Z-Harness-coevolve/.env; set +a
PATH="/Users/weichy/code/HarnessX/.venv/bin:$PATH" \
  /Users/weichy/code/HarnessX/.venv/bin/python \
  /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/tb2_eval.py \
  --env docker \
  -m deepseek-v3.2 \
  -k "$apihy_API_KEY_deepseek" \
  -b "$apihy_BASE_URL" \
  -t crack-7z-hash \
  -n 1 \
  --job-name tb2-1-h0-smoke \
  --max-steps 100
```

Result:

- Job path: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke`
- Trial: `crack-7z-hash__2FXsYpf`
- Task name: `terminal-bench/crack-7z-hash`
- Task ref: `sha256:99cbb2269f6bd112d3387fd01cb6900118fe4aded3f75a8d656580a8296a1ae5`
- Reward: `0.0`
- Exceptions: `0`
- Total runtime: `31m07s`
- Environment setup: about `10.7s`
- Agent execution: about `30m`
- Verifier runtime: about `52s`
- Harbor recorded input tokens: `1,448,375`
- HarnessX trace exit reason: `interrupted`
- HarnessX trace steps: `93`
- HarnessX trace internal cost estimate: about `$4.54` for this run; Harbor `cost_usd` remained `null`, so treat this as a provider-side estimate only.

Main artifacts:

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke/result.json
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke/crack-7z-hash__2FXsYpf/result.json
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke/crack-7z-hash__2FXsYpf/verifier/test-stdout.txt
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke/crack-7z-hash__2FXsYpf/agent/oh_runs/bb892568-cd35-4873-b7f8-0643bc4362d8.json
```

Verifier failure:

```text
FAILED ../tests/test_outputs.py::test_solution_file
AssertionError: Solution file /app/solution.txt does not exist.
FAILED ../tests/test_outputs.py::test_solution_content
FileNotFoundError: /app/solution.txt
```

## Failure Analysis

Facts from the trace:

- HarnessX produced three run segments under one session:
  - `ac26a253-84a2-491c-a02f-4d38b415180e`
  - `e78f3640-3f8f-4436-a285-79622c9356fd`
  - `518b0c7e-0d4a-42fd-9649-0f6ed40ae2d0`
- Compaction triggered at least twice and the run continued after compaction.
- Tool use was alive throughout the run; there was no tool adapter crash.
- The agent repeatedly explored:
  - password-list brute force using `7z`;
  - John the Ripper scripts and binaries;
  - `7z2john.pl`;
  - compiling John with `--disable-simd`;
  - installing `hashcat`;
  - background brute force scripts.
- Several long tool calls consumed large wall-clock chunks: examples include 60s, 85s, and 121s command durations.
- The final state had no `/app/solution.txt`.

Inference:

- This is not a Terminal-Bench 2.1 dataset mismatch, because oracle passes.
- This is not a Docker/verifier/proxy failure, because the verifier installed `curl`/`uvx`, ran tests, and returned a clean reward `0`.
- This is mainly an H0 agent-control failure:
  - The agent identifies plausible directions but does not converge.
  - It launches expensive or low-yield strategies too late.
  - It lacks a strong budget-aware policy for "abandon this line and switch".
  - It starts background work but does not ensure the required output exists before timeout.
  - It does not enforce the task's exact done condition early enough: `/app/solution.txt` must exist.

## What Was Reproduced

Reproduced successfully:

- Terminal-Bench 2.1 package dataset resolution.
- 2.1 qualified task naming and local short-name normalization.
- Local Docker environment creation and verifier execution.
- Oracle baseline on a 2.1 task.
- HarnessXAgent invocation through Harbor.
- HarnessX model-provider call path through the local API route.
- Bash tool execution in the TB2 sandbox.
- HarnessJournal trace export to `oh_runs`.
- Harbor result aggregation.
- Secret hygiene: new run artifacts store `api_key_env`, not the raw key.

Not yet reproduced:

- A passing HarnessX H0 result on Terminal-Bench 2.1.
- A fixed dev split baseline.
- Any accepted H* harness evolution.
- Any Qwen 8B training data generation or model update.

## Recommended Next H1 Change

The first H1 should be a narrow harness-only change, not model training.

Target failure cluster:

```text
Long-running terminal tasks where the model explores many plausible tool paths but does not converge to the required output file before timeout.
```

Candidate H1 components:

1. **Budget-aware command policy**
   - Before running commands expected to exceed 30-60s, require the model to state expected success signal and fallback.
   - Discourage long background brute force unless the next action explicitly checks completion and writes the required artifact.

2. **Completion file gate**
   - Add a lightweight processor/checklist that repeatedly reminds the model of exact required artifacts.
   - For file-output tasks, after any claimed success, force `ls -lh /app/solution.txt && cat /app/solution.txt`.

3. **Dependency strategy rule**
   - Prefer existing task-provided binaries/scripts over package installation or source compilation.
   - Treat package install/compile as a last resort when the timeout budget is still healthy.

4. **Loop/failure taxonomy memory**
   - Detect repeated patterns such as "try another password list slice", "compile tool", "install package", "background brute force".
   - Push the model to either extract stronger evidence or terminate the branch.

Accept gate for H1 smoke:

- Same task: `terminal-bench/crack-7z-hash`
- Same model route: `deepseek-v3.2`
- Must reduce runtime or steps materially, even if reward remains `0`.
- Must not introduce task-specific hardcoded password/answer leakage.
- Passing reward `1.0` is ideal but not required for the first H1; the minimum useful improvement is a cleaner failure with a shorter trace and clearer next action.

## Bottom Line

HarnessX reproduction is currently successful at the infrastructure and rollout-recording layers. The first real research problem is now visible: default H0 does not yet provide enough terminal-specific control to solve this 2.1 task with the chosen model. This is exactly the right point to begin harness evolution: improve the scaffold/control policy first, then collect cleaner trajectories for any later Qwen 8B update.

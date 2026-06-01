# Smoke Results

This file records small local environment checks that support the current plan. It is not a leaderboard table.

## Terminal-Bench 2.1 Oracle Smoke - 2026-06-02

Purpose: verify the active Terminal-Bench 2.1 dataset and local Docker verifier path before running H0/H* agent experiments.

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

- Dataset: `terminal-bench/terminal-bench-2-1`
- Task: `terminal-bench/crack-7z-hash`
- Job path: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-oracle-env-smoke`
- Reward: `1.0`
- Exceptions: `0`
- Runtime: `52s`

Observation: Harbor 0.13 resolves Terminal-Bench 2.1 package task names with a `terminal-bench/` prefix. The HarnessX wrapper now accepts old short names such as `crack-7z-hash` and expands them.

## Terminal-Bench 2.1 HarnessX H0 Smoke - 2026-06-02

Purpose: verify that the active HarnessXAgent path runs end to end on Terminal-Bench 2.1.

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

- Dataset: `terminal-bench/terminal-bench-2-1`
- Task: `terminal-bench/crack-7z-hash`
- Trial: `crack-7z-hash__2FXsYpf`
- Job path: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke`
- Reward: `0.0`
- Exceptions: `0`
- Runtime: `31m07s`
- Agent execution: about `30m`
- HarnessX trace: `93` steps, `1,448,375` recorded input tokens.
- Verifier failure: `/app/solution.txt` did not exist.

Observation: this proves the HarnessX rollout path works on 2.1, but H0 does not solve the task with this model/config. See [HARNESSX_TB21_REPRO_REPORT.md](HARNESSX_TB21_REPRO_REPORT.md) for the full analysis.

## Historical Terminal-Bench 2.0 H0 Smoke - 2026-06-02

Status: superseded by Terminal-Bench 2.1. Keep only as migration evidence for the local Harbor/Docker/HarnessX path.

Summary:

- Dataset: `terminal-bench@2.0`
- Task: `crack-7z-hash`
- Model: `deepseek-v3.2`
- Job path: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-h0-smoke`
- Reward: `0.0`
- Exceptions: `0`
- Runtime: `17m 6s`
- Agent execution: `15m`, then TB2 agent timeout interrupted the run.
- HarnessX trace: `78` steps, `1,043,085` recorded input tokens.

Diagnosis:

- The environment was already mostly connected: Harbor, Docker, HarnessX tool loop, trace export, and result writing worked.
- The failure was H0 policy/control: the agent spent the full timeout exploring dependency/tooling alternatives and did not write `/app/solution.txt`.
- A separate local verifier issue was found and fixed: loopback host proxies like `127.0.0.1:7897` should not be blindly forwarded into Docker verifier containers.

# Terminal-Bench 2.1 Implementation Plan

## Current Local Facts

- HarnessX clone exists at `/Users/weichy/code/HarnessX`.
- HarnessX already contains `benchmarks/terminal_bench_2`.
- `uv`, Docker, and `harbor` are installed locally.
- HarnessX adapter defaults pin `DATASET = "terminal-bench/terminal-bench-2-1"`.
- Terminal-Bench 2.1 package task names are qualified as `terminal-bench/<task>`. The HarnessX wrapper normalizes old short names such as `crack-7z-hash`.
- Oracle environment smoke passed on `terminal-bench/crack-7z-hash` with reward `1.0`.

Key local adapter files:

```text
/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/agent.py
/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/harness.py
/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/harbor_sandbox.py
/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/tb2_eval.py
```

## What To Implement First

Do not start by building a new adapter in this repository. The first correct step is to validate the existing HarnessX adapter end to end:

1. Install or expose Harbor.
2. Run dry-run command construction.
3. Run one cheap Terminal-Bench 2.1 task with local Docker.
4. Confirm result files and HarnessX `oh_runs` traces exist.
5. Write a run note before changing harness behavior.

## Smoke Commands

From the HarnessX repository:

```bash
cd /Users/weichy/code/HarnessX
uv tool install harbor
```

Dry-run one task:

```bash
python benchmarks/terminal_bench_2/scripts/tb2_eval.py \
  --env docker \
  -m "$MODEL" \
  -k "$ANTHROPIC_API_KEY" \
  -b "$ANTHROPIC_API_BASE" \
  -t crack-7z-hash \
  -n 1 \
  --job-name tb2-1-h0-smoke \
  --dry-run
```

Real smoke:

```bash
python benchmarks/terminal_bench_2/scripts/tb2_eval.py \
  --env docker \
  -m "$MODEL" \
  -k "$ANTHROPIC_API_KEY" \
  -b "$ANTHROPIC_API_BASE" \
  -t crack-7z-hash \
  -n 1 \
  --job-name tb2-1-h0-smoke
```

Expected artifacts:

```text
/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke/
.../result.json
.../agent/oh_runs/*/trace.jsonl
```

## Baseline Split

After one-task smoke succeeds, create a small dev split before any harness evolution:

- 8 to 12 tasks;
- mixed categories: software engineering, system administration, data science/security/scientific computing;
- include at least one long-running/build task and one output-file task;
- exclude known infrastructure-problem tasks until the runner is stable.

Keep a frozen held-out split separate. Do not tune on it.

## Transfer Queue

Do not mix transfer benchmarks into the first accept/revert gate. After a stable Terminal-Bench 2.1 H0/H* dev split:

1. Add τ³-bench text domains as the first text-agent transfer check.
2. Keep τ³-bench training off by default until we know whether failure modes overlap with Terminal-Bench.
3. Introduce WebArena/BALROG only after the text transfer story is interpretable.

## Harness Evolution Surface

The existing TB2 HarnessX config already exposes meaningful levers:

- system prompt checklist;
- Bash-only tool policy;
- `TaskTimeReminderProcessor`;
- `CustomSelfVerifyProcessor`;
- `CompactionProcessor`;
- `PostCompactionRefreshProcessor`;
- `CustomEditToolProcessor`;
- `BgInstallGuard`;
- `ToolCallCorrectionLayer`;
- `ParseRetryProcessor`;
- Harbor sandbox output truncation and process kill behavior.

First ablations should be narrow:

1. self-verify on/off;
2. time reminder thresholds;
3. compaction refresh behavior;
4. output truncation limit;
5. background install guard strictness;
6. prompt checklist wording.

Each proposal must name:

- failure cluster;
- expected mechanism;
- affected processor/config;
- risk;
- accept/revert criterion.

## Accept Gate

For the fixed dev split:

```text
score = pass_rate - cost_weight * max(cost_delta, 0) - infra_error_penalty
```

An H* candidate is accepted only if:

- pass rate improves or stays equal with lower cost;
- infrastructure errors do not increase materially;
- no task-specific hardcoding appears in prompt/code/config;
- held-out smoke does not regress beyond the predeclared tolerance.

## Next Deliverable

The next concrete artifact should be a tracked smoke/result note:

```text
docs/SMOKE_RESULTS.md
```

It should include command, model route, sandbox backend, task names, result paths, pass/fail, infra errors, and top failure modes. Avoid `docs/runs/`: the repo's `runs/` ignore rule treats it as local-only.

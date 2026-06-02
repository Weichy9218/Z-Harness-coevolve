# Codex Target: TB2.1 H2 Harness-Only Gate

You are Codex working locally on Z-Harness-coevolve and HarnessX. Answer in Chinese, keep technical terms in English.

## Objective

Prove or reject H2 harness-only gain before any model training.

Primary comparison:

- Same baseline model M0: `deepseek-v3.2`
- Same API base: `https://zgc.apihy.com/v1`
- Same sandbox: HarnessX local Docker / `DinDDockerEnvironment` with `network_mode=host`
- Same benchmark: `terminal-bench/terminal-bench-2-1`
- Same dev split: `/Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_dev_v0.tasks.json`

Do not train Qwen 8B. Do not vendor Terminal-Bench data. Do not migrate HarnessX into Z-Harness-coevolve.

## Repo Roles

- `/Users/weichy/code/HarnessX`: runnable substrate, harness processors, wrappers, TB2 eval.
- `/Users/weichy/code/Z-Harness-coevolve`: experiment controller, split manifest, run notes, ablation reports, future exporter/sanitizer.

## Current H2 Status

H2 is implemented in HarnessX local worktree:

- `ToolTimeoutStrategyProcessor`: if a heavy install/build times out, prevent repeated default-timeout retries; allow one explicit `timeout=600000` retry.
- `SlowBruteforceGuardProcessor`: block unbounded wordlist loops that invoke external cracking/extraction commands per candidate.
- Bounded probes are allowed: `head -N`, `timeout N`, small `range(N)`, `islice(...)`, and small literal shell `for var in ...; do` loops with at most 32 candidates.
- H1b `AptInstallRecoveryProcessor` remains enabled.

Focused verification already passed:

```bash
PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
python -m pytest tests/unit/test_tb2_harness_processors.py -q

PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
python -m pytest tests/unit/test_harness_config_hydra.py tests/unit/test_tb2_harness_processors.py -q
```

Expected results at the time this target was written:

- `12 passed`
- `24 passed`

## Immediate Next Step

Run the H2c single-task gate only after `TB2_API_KEY` is available in the shell:

```bash
PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
TB2_MODEL=deepseek-v3.2 \
TB2_API_BASE=https://zgc.apihy.com/v1 \
TB2_API_KEY="$TB2_API_KEY" \
bash /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  -t crack-7z-hash \
  --job-name tb2-1-h2c-tool-cost-crack-gate-20260602 \
  -n 1 \
  --max-steps 100 \
  --request-timeout-sec 600
```

H2c gate is clean if it either:

- passes `crack-7z-hash`, or
- fails without repeating the H1b failure loop: no repeated default-timeout heavy install and no long unbounded per-password `7z` loop.

If H2c exposes a new false positive or false negative, stop the run, inspect trace first, add a regression test, patch the processor, rerun focused tests, then rerun a new gate with a new job name.

## Then Run Dev Ablation

Only after H2c is clean:

1. Run H0/M0 on the fixed dev split from a pinned H0 HarnessX commit/config or a separate clean worktree.
2. Run H2/M0 on the same dev split from the H2 HarnessX worktree.
3. Keep model route, sandbox backend, concurrency, max steps, and request timeout identical.
4. Record reward/pass, runtime, steps, token count, tool-call count, infra errors, verifier failures, and artifact paths.

Do not use held-out tasks during harness tuning. Do not start trajectory exporter/sanitizer until H* is frozen.

## Reporting File

Update:

```bash
/Users/weichy/code/Z-Harness-coevolve/docs/HARNESSX_TB21_HARNESS_ONLY_ABLATION.md
```

Include:

- HarnessX commit or dirty worktree diff summary.
- Exact command.
- Artifact root.
- Trial result path.
- oh_runs trace path.
- Processor signals observed.
- Pass/reward/runtime/token/tool-call counts.
- Whether the gate is accepted, rejected, or invalid.

Also update the machine-readable run ledger:

```bash
/Users/weichy/code/Z-Harness-coevolve/experiments/tb2_1_harness_only/run_ledger.json
```

## Pre-Training Prep

Training export must remain fail-closed until H* is frozen.  The current train
split scaffold is intentionally empty:

```bash
/Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_train_v0.tasks.json
```

Use this exporter only after accepted H* train trajectories exist:

```bash
PATH=/Users/weichy/code/Z-Harness-coevolve/.venv/bin:$PATH \
python /Users/weichy/code/Z-Harness-coevolve/scripts/tb2_export_sft_candidates.py \
  --ledger /Users/weichy/code/Z-Harness-coevolve/experiments/tb2_1_harness_only/run_ledger.json \
  --split-manifest /Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_only_v0_manifest.json \
  --output /Users/weichy/code/Z-Harness-coevolve/artifacts/tb2_1_harness_only/sft_candidates.jsonl
```

Expected before H* is frozen: `n_candidates = 0`.

# HarnessX TB2.1 Harness-Only Ablation

Core decision: keep HarnessX external. Z-Harness-coevolve is the experiment controller; HarnessX is the runnable substrate; Terminal-Bench 2.1 is the primary loop. tau-bench and tau3-bench stay as later transfer checks, not first-round inner-loop tasks.

## Evidence Read

Requested direction docs were not present in Z-Harness-coevolve during this inspection:

- `docs/DIRECTION.md`
- `docs/HARNESSX_SIA_FLOW.md`
- `docs/TERMINAL_BENCH_2_PLAN.md`
- `docs/HARNESSX_TB21_REPRO_REPORT.md`
- `docs/QWEN8B_TRAINING_PLAN.md`

Existing Z README still describes the older MiniLang/API-only phase. HarnessX has the active TB2 substrate under `/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/`.

## H0 Smoke

Artifact root: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke`

- Dataset: `terminal-bench/terminal-bench-2-1`
- Dataset ref: `sha256:7d7bdc1cbedad549fc1140404bd4dc45e5fd0ea7c4186773687d177ad3a0699a`
- HarnessX commit observed: `76f24218b5ad8e0e880326aab102f9002752fca3`
- Model: `deepseek-v3.2`
- API base: `https://zgc.apihy.com/v1`
- Sandbox: `DinDDockerEnvironment`, `network_mode=host`
- Task: `terminal-bench/crack-7z-hash`
- Task ref: `sha256:99cbb2269f6bd112d3387fd01cb6900118fe4aded3f75a8d656580a8296a1ae5`
- Reward: `0.0`
- Infra errors: `0`
- Verifier failure: `/app/solution.txt` missing
- Agent execution: about 1800s
- Reported input tokens: `1448375`
- Observed Bash tool calls: `93`

Failure cluster: tool availability/install recovery. The model found the 7z/JTR path, but the bundled `john` binary required AVX2. `hashcat` install then failed with stale apt package URLs/404. The model did not run `apt-get update`, likely because H0 prompt says not to, then fell back to slow per-password `7z` brute force and timed out without writing `solution.txt`.

## H1 Proposal

Name: `h1b_strict_apt_install_recovery`

Scope: harness-only. Do not change model, benchmark data, task selection, verifier, or task-specific answer logic.

Failure cluster:

- `apt-get install` fails with stale package metadata, 404, or "Unable to fetch some archives".
- The model has a valid tool strategy but loses time after a recoverable install failure.
- H0 prompt makes `apt-get update` an absolute prohibition, so the model avoids the correct recovery.

Expected mechanism:

- Block preemptive `apt-get update` before any install failure is observed.
- Permit exactly one synchronous `apt-get update` after an observed stale-index install failure.
- Inject a one-shot tool-result warning at the moment of failure so the model retries the same install instead of switching to a slow fallback.
- Keep this generic: no task names, no password hints, no verifier access.

Changed config/code:

- In `/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/harness.py`, revise `_TB2_SYSTEM` workflow item 9 from an absolute ban to:
  `Prefer apt-get install directly. Do not run apt-get update preemptively; the harness may block it. If apt-get install fails with stale package metadata, 404, Hash Sum mismatch, or "Unable to fetch", run one synchronous apt-get update, then retry the same install once.`
- Add `AptInstallRecoveryProcessor(MultiHookProcessor)` in the same file:
  - Track Bash commands containing `apt-get install`.
  - Block Bash commands containing `apt-get update` until a stale install failure has occurred.
  - On the first matching tool result with stale apt failure patterns, append a corrective message allowing one synchronous `apt-get update` followed by a retry of the same install.
  - Reset the one-shot state on task start/end.
- Add `.add(AptInstallRecoveryProcessor())` to `make_tb2_harness_config()`, near `BgInstallGuard()`.
- Fix the local Docker and OpenSandbox wrappers to support documented `-t <task>` usage under macOS Bash 3.2 + `set -u` by avoiding empty-array expansion.

Risk:

- Runtime can increase on tasks where package lists are stale and network is slow.
- More package installs may mask a weak direct solution strategy.
- Network-dependent apt behavior can introduce variance even with the same model route.
- It may not solve failures caused by CPU feature mismatch, missing internet, or fundamentally wrong reasoning.

Accept criterion:

- Full dev split H1/M0 has at least one more pass than H0/M0 with the same model route and sandbox backend.
- No H0 pass becomes an H1 fail unless the failure is clearly infra and reproduced on rerun.
- Infra errors do not increase.
- Median runtime and token count do not grow by more than 20%.
- Initial single-task gate: `crack-7z-hash` should either pass or move out of the apt-install/slow-bruteforce failure cluster.

Revert criterion:

- No pass gain on the dev split.
- New apt-induced verifier or infra failures.
- Runtime/token overhead exceeds the 20% guardrail without a pass gain.
- Evidence shows the change only helps `crack-7z-hash` through task-specific behavior.

## H2 Proposal

Name: `h2_tool_cost_and_bruteforce_guard`

Scope: harness-only on top of H1b. Do not change model, benchmark data, task selection, verifier, or task-specific answer logic.

Failure cluster:

- H1b fixes stale apt policy, but heavyweight installs can still consume the Bash timeout or pull very large dependency sets.
- After expensive tool paths fail, the model tends to fall back to slow per-candidate archive extraction.
- The model needs a generic cost policy: bounded probes are OK; unbounded wordlist loops are not.

Expected mechanism:

- If a heavyweight install/build command times out, append a `ToolTimeoutStrategy` hint.
- Block repeating the same heavyweight command with the default Bash timeout; allow exactly one explicit long retry with `timeout=600000` if the model says that path is essential.
- Block obvious unbounded wordlist loops that invoke external cracking/extraction commands per candidate.
- Allow bounded probes, including `head -N`, `timeout N`, small `range(N)`, `islice(...)`, and small literal shell `for var in ...; do` candidate lists.

Changed config/code:

- In `/Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/harness.py`, add:
  - `ToolTimeoutStrategyProcessor`
  - `SlowBruteforceGuardProcessor`
  - `_has_bounded_bruteforce_probe(...)`
- Add both processors to `make_tb2_harness_config()`.
- Add prompt item 10: bound expensive search before wordlist/brute-force/batch commands.
- Add focused unit coverage in `/Users/weichy/code/HarnessX/tests/unit/test_tb2_harness_processors.py`.

Risk:

- False positives can block useful small probes.
- False negatives can still allow library-level brute force if the command does not look like a wordlist loop.
- Heavy install retry policy may be too strict for tasks where a long install is the only viable path.
- Tool-timeout behavior is network-sensitive and may not trigger on stale apt/404 failures.

Accept criterion:

- Single-task gate on `crack-7z-hash` either passes or exits the H1b failure loop: no repeated default-timeout heavy install and no long unbounded per-password `7z` loop.
- Focused processor tests and HarnessConfig round-trip tests pass.
- Full dev split H2/M0 has at least one more pass than H0/M0 with the same model route, sandbox backend, task split, and limits.
- H2 does not regress an H0 pass unless the regression is clear infra and reproduced.
- Median runtime/token/tool-call overhead remains within the 20% guardrail unless there is a pass gain.

Revert criterion:

- H2 blocks common bounded probes without a compensating pass gain.
- H2 allows the same slow brute-force loop that motivated the change.
- H2 increases infra errors or verifier failures on the dev split.
- No dev split pass gain over H0/M0.

## Gate Attempts

H1a prompt-only run:

- Job: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h1-apt-recovery-crack-gate-20260602`
- Status: manually stopped before verifier; do not count in metrics.
- Reason: mechanism was not clean. The model ran preemptive `apt-get update && apt-get install -y p7zip-full`, then drifted back into brute-force cracking.
- Evidence: 38 Bash tool calls before stop, no `AptInstallRecovery` policy signal.

H1b strict apt gate run:

- Job: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h1b-strict-apt-gate-crack-20260602`
- Status: manually stopped before verifier; do not count as pass/fail metric.
- Mechanism evidence: step 3 preemptive `apt-get update && apt-get install -y p7zip-full` was blocked by `AptInstallRecovery`; step 4 direct `apt-get install -y p7zip-full` proceeded. Later, direct `apt-get install -y hashcat` triggered the recovery path, and one `apt-get update` was allowed.
- Outcome evidence: retrying `apt-get install -y hashcat` timed out after 120s. The model then returned to slow per-password `7z` brute force.
- Interpretation: H1b fixes the stale apt policy mechanism but does not pass `crack-7z-hash`; the next H candidate should address heavy install/tool-timeout and slow cracking strategy, not model training.

H2a tool-cost/bruteforce gate run:

- Job: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h2-tool-cost-crack-gate-20260602`
- Status: manually stopped before verifier; do not count as pass/fail metric.
- Invalid reason: first `SlowBruteforceGuard` version treated Python preview slices such as `password[:20]` as bounded loop evidence, so an unbounded wordlist/external-command loop was not blocked.
- Fix: remove the generic Python slice pattern from bounded-loop detection and add a regression test.

H2b tool-cost/bruteforce gate run:

- Job: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h2b-tool-cost-crack-gate-20260602`
- Status: manually stopped before verifier; do not count as pass/fail metric.
- Mechanism evidence:
  - step 3 preemptive `apt-get update && apt-get install -y p7zip-full` was blocked by `AptInstallRecovery`.
  - step 20 large Python common-password brute-force script was blocked by `SlowBruteforceGuard`.
  - step 27 small literal shell loop with 9 candidate passwords was also blocked.
- Invalid reason: step 27 was a bounded sample and should have been allowed. This was a false positive against H2's own policy.
- Fix: add `_has_bounded_bruteforce_probe(...)` support for small literal shell `for var in ...; do` loops with at most 32 candidates and no variable expansion, command substitution, glob, pipe, or path source. Add regression coverage for both allowed small literal probes and blocked large literal probes.
- Trace summary before stop: 32 Bash calls, 32 assistant steps, `AptInstallRecovery` once, `SlowBruteforceGuard` twice, about 372777 input tokens and 7569 output tokens from raw assistant usage records.

H2c gate status:

- Prepared but not run in this Codex shell because `TB2_API_KEY` is unset.
- Dry-run command sanity passed for job `tb2-1-h2c-tool-cost-crack-gate-20260602`; Harbor target is dataset `terminal-bench/terminal-bench-2-1`, task `terminal-bench/crack-7z-hash`, environment `DinDDockerEnvironment`, `network_mode=host`.
- Required next action: export a valid `TB2_API_KEY` and run the H2c single-task gate before any 10-task dev ablation.

## Split Manifest

Detailed manifest: `/Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_only_v0_manifest.json`

Train split scaffold, intentionally empty until H* is frozen:

```bash
/Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_train_v0.tasks.json
```

Runnable dev task list:

```bash
/Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_dev_v0.tasks.json
```

Held-out task list, not for H1 tuning:

```bash
/Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_heldout_v0.tasks.json
```

Before using the split in a paper table, verify every task against the active Harbor dataset ref with `harbor dataset download terminal-bench/terminal-bench-2-1 --cache` or an equivalent Harbor metadata listing. Do not copy task files into this repo.

## Verification Commands

Use the same task split, model route, sandbox backend, and limits for H0/M0 and H*/M0.
Run these from the HarnessX environment, or prefix `PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH`; otherwise the wrapper can fail with `ModuleNotFoundError: No module named 'harbor'`.
Because the built-in HarnessX config now contains H2 processors in the local worktree, run H0/M0 from a pinned H0 HarnessX commit/config or a separate clean worktree. Do not label the current dirty H2 worktree as H0.

Dry-run command sanity:

```bash
PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
TB2_MODEL=deepseek-v3.2 \
TB2_API_BASE=https://zgc.apihy.com/v1 \
TB2_API_KEY=DUMMY \
bash /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  --tasks /Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_dev_v0.tasks.json \
  --job-name tb2-1-dev-h0-m0-20260602 \
  -n 1 \
  --max-steps 100 \
  --request-timeout-sec 600 \
  --dry-run
```

H0/M0 dev run:

```bash
PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
TB2_MODEL=deepseek-v3.2 \
TB2_API_BASE=https://zgc.apihy.com/v1 \
TB2_API_KEY="$TB2_API_KEY" \
bash /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  --tasks /Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_dev_v0.tasks.json \
  --job-name tb2-1-dev-h0-m0-20260602 \
  -n 1 \
  --max-steps 100 \
  --request-timeout-sec 600
```

H1/M0 dev run after applying the HarnessX H1 patch:

```bash
PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
TB2_MODEL=deepseek-v3.2 \
TB2_API_BASE=https://zgc.apihy.com/v1 \
TB2_API_KEY="$TB2_API_KEY" \
bash /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  --tasks /Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_dev_v0.tasks.json \
  --job-name tb2-1-dev-h1-apt-recovery-m0-20260602 \
  -n 1 \
  --max-steps 100 \
  --request-timeout-sec 600
```

H2c single-task gate after exporting a valid `TB2_API_KEY`:

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

H2/M0 dev run only after the H2c gate is clean:

```bash
PATH=/Users/weichy/code/HarnessX/.venv/bin:$PATH \
TB2_MODEL=deepseek-v3.2 \
TB2_API_BASE=https://zgc.apihy.com/v1 \
TB2_API_KEY="$TB2_API_KEY" \
bash /Users/weichy/code/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  --tasks /Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_dev_v0.tasks.json \
  --job-name tb2-1-dev-h2-tool-cost-m0-20260602 \
  -n 1 \
  --max-steps 100 \
  --request-timeout-sec 600
```

Record each trial's `result.json`, `agent/oh_runs`, verifier stdout, reward, runtime, token count, and exception fields. Only after H* is frozen should held-out tasks be evaluated.

## Run Ledger And Export

Machine-readable run ledger:

```bash
/Users/weichy/code/Z-Harness-coevolve/experiments/tb2_1_harness_only/run_ledger.json
```

Summarize a Harbor job artifact:

```bash
PATH=/Users/weichy/code/Z-Harness-coevolve/.venv/bin:$PATH \
python /Users/weichy/code/Z-Harness-coevolve/scripts/tb2_summarize_job.py \
  /Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke \
  --output /Users/weichy/code/Z-Harness-coevolve/artifacts/tb2_1_harness_only/h0_smoke_summary.json
```

Export accepted SFT candidates after H* is frozen:

```bash
PATH=/Users/weichy/code/Z-Harness-coevolve/.venv/bin:$PATH \
python /Users/weichy/code/Z-Harness-coevolve/scripts/tb2_export_sft_candidates.py \
  --ledger /Users/weichy/code/Z-Harness-coevolve/experiments/tb2_1_harness_only/run_ledger.json \
  --split-manifest /Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_only_v0_manifest.json \
  --output /Users/weichy/code/Z-Harness-coevolve/artifacts/tb2_1_harness_only/sft_candidates.jsonl
```

Current expected export result: `n_candidates = 0`; this is correct before H*/M0 is accepted and train-split trajectories exist.

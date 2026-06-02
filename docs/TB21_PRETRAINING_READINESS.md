# TB2.1 Pre-Training Readiness

Date: 2026-06-02

This note records the current state before any Qwen 8B training.  It separates
facts, inferences, and remaining blockers so training does not start from an
unstable harness story.

## Current Position

Do not train yet.

The next scientific gate is still H*/M0 harness-only gain on Terminal-Bench 2.1:

- baseline model M0: `deepseek-v3.2`
- benchmark: `terminal-bench/terminal-bench-2-1`
- sandbox: HarnessX local Docker / `DinDDockerEnvironment`, `network_mode=host`
- controller repo: `/Users/weichy/code/Z-Harness-coevolve`
- runnable substrate: `/Users/weichy/code/HarnessX`

The H2 harness patch is implemented and unit-tested locally, but the H2c
single-task gate has not run in this shell because `TB2_API_KEY` is unset.

## What Was Done Right

### Repo boundary is correct

HarnessX was not copied into Z-Harness-coevolve.  This is the right boundary:

- HarnessX owns runnable benchmark integration, harness processors, wrappers,
  tool policy, and sandbox behavior.
- Z-Harness-coevolve owns experiment control, split manifests, run ledgers,
  reports, and future export/sanitize logic.

This keeps the experimental story reproducible without vendoring a moving
substrate or benchmark data.

### H0 failure was diagnosed from artifacts

The H0 smoke conclusion is artifact-backed:

- job: `/Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke`
- task: `terminal-bench/crack-7z-hash`
- reward: `0.0`
- verifier failure: missing `/app/solution.txt`
- observed Bash calls: `93`
- reported input tokens: `1448375`

The failure cluster is not "Terminal-Bench is broken"; it is a harness/runtime
strategy issue:

- existing `john` binary required AVX2;
- `hashcat` install hit stale apt package URLs / 404;
- H0 prompt discouraged `apt-get update`;
- model drifted into slow per-password `7z` brute force and exhausted budget.

### H1 was scoped correctly

H1b addressed one generic mechanism: stale apt recovery.  It did not add a
task-specific answer or model change.  The processor blocks preemptive
`apt-get update`, then permits exactly one update after a real stale install
failure.

This is a valid harness-only change, even though it was not sufficient to pass
`crack-7z-hash`.

### H2 was designed from H1b residual failure

H1b exposed the next mechanism:

- heavyweight installs can still consume budget;
- after install trouble, the model falls back to slow brute force.

H2 therefore adds:

- `ToolTimeoutStrategyProcessor`
- `SlowBruteforceGuardProcessor`
- prompt item for bounded expensive search

It remains harness-only and generic.

### False positives/false negatives were treated as invalid gates

H2a and H2b were not counted as wins:

- H2a missed an unbounded loop because a preview slice was misread as a bounded
  loop.
- H2b blocked a small literal password probe that should have been allowed.

Both were fixed with regression tests before any dev ablation.  This is the
right discipline: invalid gates should improve the harness policy, not become
metrics.

### Training export is now fail-closed

The new export path only emits SFT candidate records when all are true:

- run ledger entry has `split=train`;
- entry is `status=completed`;
- entry has `accepted_for_training=true`;
- Harbor verifier reward is `1.0`;
- task is not held-out/test.

Current result: zero training candidates.  That is correct.

## What Was Not Done Well

### H1a/H1b/H2a/H2b job metadata remains half-finished upstream

Several manually stopped Harbor jobs still have job-level `result.json` with
`n_running_trials: 1` and no completed trial result.  The prose docs explain
they are invalid, but Harbor job metadata itself is stale.

Mitigation now:

- these runs are marked `invalid_stopped` in
  `experiments/tb2_1_harness_only/run_ledger.json`;
- exporter ignores them.

Remaining issue:

- if a future tool scans Harbor job stats directly, it may misread them as
  running jobs unless it consults the ledger.

### H2c was not actually run

The dry-run passed, but no real H2c trial exists yet.  The shell environment
does not contain `TB2_API_KEY`, so launching the real gate here would fail.

This is a hard blocker for claiming H2 mechanism improvement.

### Dev split is still a scaffold

The 10-task dev split is tracked, but the task list was not verified against a
fresh Harbor metadata listing.  The manifest explicitly records this as TODO.

This is acceptable for local preparation, but not for a paper table or a final
ablation claim.

### Train split is intentionally empty

A train split scaffold now exists:

```bash
/Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_train_v0.tasks.json
```

It is empty by design.  Filling it before H* is frozen would blur harness tuning
and training data collection.

### Exporter is a sanitizer scaffold, not a proof of leakage safety

The exporter redacts obvious task IDs, trial IDs, local paths, verifier artifact
paths, hashes, and literal solution writes.  This is useful, but not enough for
high-confidence leakage control.

Still missing:

- sampled human review protocol;
- automated task-specific answer scanner per TB2 task family;
- held-out/test contamination check against all candidate outputs;
- explicit decision on whether final answer-writing steps are kept, redacted, or
  dropped.

## What Is Still Missing Before Training

### Required before any training

1. Run H2c single-task gate on `crack-7z-hash`.
2. If H2c is invalid, patch H2 with regression tests and rerun a new gate.
3. If H2c is clean, run same-split H0/M0 vs H2/M0 10-task dev ablation.
4. Verify the 10 dev tasks against active Harbor TB2.1 metadata.
5. Freeze H* and record HarnessX exact commit or patch diff.
6. Create a real train split that excludes dev tuning and heldout tasks.
7. Collect accepted H* train trajectories only.
8. Export sanitized SFT candidate JSONL.
9. Run leakage scanner and sampled human review on candidate records.
10. Only then prepare Qwen 8B SFT/LoRA configs.

### Useful but not blocking for H2c

- Clean up stale Harbor job metadata for manually stopped diagnostic runs.
- Add a summary table generator from `run_ledger.json` + summaries.
- Decide whether tau-bench/tau3-bench transfer checks need their own split
  manifests now or after TB2 dev ablation.

## Prepared Commands

H2c gate:

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

Summarize a Harbor job:

```bash
PATH=/Users/weichy/code/Z-Harness-coevolve/.venv/bin:$PATH \
python /Users/weichy/code/Z-Harness-coevolve/scripts/tb2_summarize_job.py \
  /Users/weichy/code/HarnessX/.benchmarks/tb2/tb2-1-h0-smoke \
  --output /Users/weichy/code/Z-Harness-coevolve/artifacts/tb2_1_harness_only/h0_smoke_summary.json
```

Export accepted SFT candidates:

```bash
PATH=/Users/weichy/code/Z-Harness-coevolve/.venv/bin:$PATH \
python /Users/weichy/code/Z-Harness-coevolve/scripts/tb2_export_sft_candidates.py \
  --ledger /Users/weichy/code/Z-Harness-coevolve/experiments/tb2_1_harness_only/run_ledger.json \
  --split-manifest /Users/weichy/code/Z-Harness-coevolve/splits/terminal_bench_2_1/harness_only_v0_manifest.json \
  --output /Users/weichy/code/Z-Harness-coevolve/artifacts/tb2_1_harness_only/sft_candidates.jsonl
```

Expected current export result: `n_candidates = 0`.


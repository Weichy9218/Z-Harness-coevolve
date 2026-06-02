# Server Bootstrap: TB2.1 Harness-Only Prep

Date: 2026-06-02

Use this when starting from a fresh server clone.  Z-Harness-coevolve remains the
experiment controller; HarnessX remains the runnable substrate.

## Clone

```bash
git clone git@github.com:Weichy9218/Z-Harness-coevolve.git /path/to/Z-Harness-coevolve
git clone https://github.com/Darwin-Agent/HarnessX.git /path/to/HarnessX
```

The local HarnessX H2 commit could not be pushed to `Darwin-Agent/HarnessX`
because the current GitHub credential does not have upstream write permission.
Apply the tracked patch from Z-Harness-coevolve instead:

```bash
cd /path/to/HarnessX
git checkout -b codex/tb2-1-adapter
git am /path/to/Z-Harness-coevolve/patches/harnessx/0001-tb2-h2-harness-only-guards.patch
```

Expected local HarnessX patch commit subject:

```text
Add TB2 harness-only H2 guards
```

## Verify Local Prep

Z-Harness-coevolve:

```bash
cd /path/to/Z-Harness-coevolve
python -m pytest -q
```

HarnessX:

```bash
cd /path/to/HarnessX
python -m pytest tests/unit/test_harness_config_hydra.py tests/unit/test_tb2_harness_processors.py -q
```

Expected results from the local Mac state:

- Z-Harness-coevolve: `18 passed`
- HarnessX targeted tests: `24 passed`

## H2c Gate Before Training

Do not start Qwen 8B training before H2c and the dev ablation are resolved.
First configure the model route:

```bash
export TB2_MODEL=deepseek-v3.2
export TB2_API_BASE=https://zgc.apihy.com/v1
export TB2_API_KEY=...
```

Then run:

```bash
PATH=/path/to/HarnessX/.venv/bin:$PATH \
bash /path/to/HarnessX/benchmarks/terminal_bench_2/scripts/eval_local_docker.sh \
  -t crack-7z-hash \
  --job-name tb2-1-h2c-tool-cost-crack-gate-20260602 \
  -n 1 \
  --max-steps 100 \
  --request-timeout-sec 600
```

Update the run ledger after the gate:

```bash
/path/to/Z-Harness-coevolve/experiments/tb2_1_harness_only/run_ledger.json
```

Only after a clean H2c gate should you run the same-split H0/M0 vs H2/M0
10-task dev ablation.  Training export remains fail-closed until H* is frozen
and accepted train-split trajectories exist.

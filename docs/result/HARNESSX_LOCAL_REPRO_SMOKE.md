# HarnessX Local Reproduction Smoke

This note records the local no-GPU HarnessX reproduction attempt on
2026-06-01. It separates what is already runnable from what still needs a
stronger API model, API budget, or GPU training.

## Local Checkout

HarnessX was cloned outside this repo:

```text
/Users/weichy/code/HarnessX
```

Checkout:

```text
6fdf899
```

Setup:

```bash
cd /Users/weichy/code/HarnessX
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
uv pip install socksio
```

`socksio` was installed because LiteLLM attempted to use the local SOCKS proxy
when fetching its remote model cost map.

## Import and CLI Smoke

Import smoke:

```bash
/Users/weichy/code/HarnessX/.venv/bin/python - <<'PY'
import harnessx
from harnessx import BaseTask, HarnessConfig
from harnessx.core.model_config import ModelConfig
print("harnessx_import=ok")
print("BaseTask=", BaseTask.__name__)
print("HarnessConfig=", HarnessConfig.__name__)
print("ModelConfig=", ModelConfig.__name__)
PY
```

Result:

```text
harnessx_import=ok
BaseTask= BaseTask
HarnessConfig= HarnessConfig
ModelConfig= ModelConfig
```

CLI help works:

```bash
/Users/weichy/code/HarnessX/.venv/bin/hx --help
```

GAIA evolver help works:

```bash
/Users/weichy/code/HarnessX/.venv/bin/python -m recipe.gaia_evolver.run --help
```

## HarnessX Unit Tests

Run:

```bash
/Users/weichy/code/HarnessX/.venv/bin/python -m pytest tests/unit -q
```

Result:

```text
861 passed, 5 skipped, 1 failed
```

The single failure is macOS-specific path canonicalization:

```text
tests/unit/test_workspace_home.py::TestWorkspaceHome::test_no_mode_allows_any_path
expected /etc/passwd, observed /private/etc/passwd
```

This does not block the local HarnessX smoke, but it should be noted if we make
HarnessX tests part of a CI gate on macOS.

## Local GAIA-Style Smoke

Because the repo checkout does not include `recipe/gaia_evolver/data/`, a
minimal local text-only GAIA-style task was created at:

```text
/Users/weichy/code/HarnessX/recipe/gaia_evolver/data/smoke_gaia.json
```

Task:

```text
What is 2 + 2? Answer with only the number.
```

### R0 Baseline Smoke

Run:

```bash
set -a
source /Users/weichy/code/Z-Harness-coevolve/.env
set +a
/Users/weichy/code/HarnessX/.venv/bin/python -m recipe.gaia_evolver.run \
  --max-tasks 1 \
  --num-rounds 1 \
  --model gpt-4o-mini \
  --meta-model gpt-4o-mini \
  --provider-id openai \
  --max-cost 0.25 \
  --max-steps 1 \
  --concurrency 1 \
  --no-judge \
  --data-path recipe/gaia_evolver/data/smoke_gaia.json \
  --run-tag local_smoke_no_gpu \
  --clean
```

Result:

```text
pass=1/1
cost=$0.009
tokens=2920
steps=1
```

Artifacts:

```text
/Users/weichy/code/HarnessX/recipe/gaia_evolver/runs/local_smoke_no_gpu/
├── R0/config.yaml
├── R0/sessions/R0-local-smoke-001.json
├── R0/trajectories/local-smoke-001.md
└── comparison.json
```

This verifies the HarnessX task runner, GAIA JSON adapter, trajectory writer,
session writer, and comparison summary without GPU.

### Two-Round Evolver Smoke

Run:

```bash
set -a
source /Users/weichy/code/Z-Harness-coevolve/.env
set +a
/Users/weichy/code/HarnessX/.venv/bin/python -m recipe.gaia_evolver.run \
  --max-tasks 1 \
  --num-rounds 2 \
  --model gpt-4o-mini \
  --meta-model gpt-4o-mini \
  --provider-id openai \
  --max-cost 0.25 \
  --max-steps 1 \
  --concurrency 1 \
  --no-judge \
  --evolve-cost 1.00 \
  --evolve-steps 15 \
  --evolve-wall-clock 240 \
  --pass-count-noise-threshold 0 \
  --data-path recipe/gaia_evolver/data/smoke_gaia.json \
  --run-tag local_evolver_no_gpu_v2 \
  --clean
```

Result:

| round | pass | cost | tokens | evolve status |
| --- | ---: | ---: | ---: | --- |
| R0 | 1/1 | 0.009 | 2920 | baseline |
| R1 | 1/1 | 0.009 | 2920 | crashed |

Artifacts:

```text
/Users/weichy/code/HarnessX/recipe/gaia_evolver/runs/local_evolver_no_gpu_v2/
├── R0/config.yaml
├── R0/trajectories/local-smoke-001.md
├── R1/config.yaml
├── R1/evolve/_meta_scratch/DECISION_REQUIRED.md
├── R1/trajectories/local-smoke-001.md
└── comparison.json
```

The outer loop did run R0, attempted `MetaAgent.evolve()`, handled the missing
candidate config, reused the current config, and completed R1. The failure mode
was explicit:

```text
meta-agent finished but did not produce R1/evolve/config.yaml
```

`DECISION_REQUIRED.md` says the meta-agent must either write a changed
`config.yaml` or explicitly copy the previous config as a no-op.

## Interpretation

Current no-GPU HarnessX reproduction status:

- Core install: works.
- CLI/import: works.
- GAIA adapter and trajectory/session filesystem: works.
- One-round local benchmark smoke: works.
- Two-round outer loop: runs and recovers from meta-agent failure, but the
  OpenAI mini-model did not complete the required config-writing contract.

This is enough to study HarnessX's artifact contract locally. It is not a
full reproduction of HarnessX's reported GAIA gains.

Full HarnessX reproduction still requires one of:

- Anthropic-compatible meta/judge credentials as assumed by the recipe defaults;
- a stronger OpenAI-compatible meta-agent configuration that reliably writes
  `output_dir/config.yaml`;
- real GAIA/WebThinker data and a larger API budget;
- GPU only for `recipe/verl_harnessX` model-evolution training.

For this project, the useful takeaway remains the artifact protocol:
`config.yaml`, per-task trajectories, `sessions/`, `comparison.json`,
`learnings.md`, and explicit evolve failure notes.

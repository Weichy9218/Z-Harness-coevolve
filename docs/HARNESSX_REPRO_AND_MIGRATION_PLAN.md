# HarnessX Reproduction and Migration Plan

本文件把 HarnessX 复现路线和本项目的迁移计划放在一起。目标不是把
HarnessX 当成 novelty，而是借它的工程协议来稳住本项目的 experience
allocation 实验。

## Current Reading

HarnessX 的核心对象不是单个 benchmark，而是可组合、可演化的 agent
harness：

- `ModelConfig` 负责 provider routing、fallback、role-specific model。
- `HarnessConfig` 负责 tools、memory、processors、trace、sandbox。
- Behavior 由 processors 组成，挂在 event-driven hook pipeline 上。
- 每轮运行生成 reward-annotated trajectories，可导出给 SFT / RL。
- GAIA evolver 的外层 loop 是：run tasks -> save trajectories ->
  meta-agent writes next config -> best-so-far gate / revert。

公开 repo 当前展示的 benchmark adapters 包括 GAIA、Terminal-Bench 2、
SWE-bench、TAU2-Bench；model-evolution recipe 走 `verl_harnessX`，full
training 需要 CUDA / GPU。Harness-only evolution 可以用 API model 在 CPU
机器上复现。

Sources checked on 2026-05-31:

- HarnessX README: https://github.com/Darwin-Agent/HarnessX/blob/main/README.md
- HarnessX benchmarks: https://github.com/Darwin-Agent/HarnessX/blob/main/benchmarks/README.md
- GAIA evolver recipe: https://github.com/Darwin-Agent/HarnessX/blob/main/recipe/gaia_evolver/README.md
- verl_harnessX recipe: https://github.com/Darwin-Agent/HarnessX/blob/main/recipe/verl_harnessX/README.md

## What To Borrow

Borrow the execution protocol, not the claim.

1. Processor / hook structure
   - Map `k_gen_interactive` into explicit actions:
     observe examples -> propose hypothesis -> request minimal pair /
     counterexample -> verifier feedback -> repair -> final audit.
   - Keep these actions as structured records, not just prompt text.

2. Trajectory filesystem
   - Save per-episode JSONL records, task-level verifier outputs, cost, token
     usage, action trace, and config lineage.
   - Add project-specific fields that HarnessX does not decide for us:
     `leakage_flags`, `source_specificity`, `counterfactual_delta`,
     `heldout_delta`, and robust adoption decision.

3. Best-so-far gate
   - Use HarnessX-style keep/revert for harness configs.
   - Replace naive pass-rate-only gating with robust adoption:
     counterfactual and heldout removal deltas must be non-negative within
     tolerance before an item can become a promotion candidate.

## What Not To Borrow

- Do not use GAIA as the first proof of quarantine boundary. It is useful for
  external validation, but it entangles web retrieval, open-world knowledge,
  model priors, and harness behavior.
- Do not treat raw successful trajectories as trainable data. Raw SFT remains
  a leakage control arm.
- Do not promote source-specific rulebooks because they improve seen-family
  score. They must pass no-specific-harness, counterfactual, and heldout gates.

## No-GPU Reproduction Track

This track is feasible on the current machine if API credentials are available.

```bash
git clone https://github.com/Darwin-Agent/HarnessX
cd HarnessX
uv python install 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e .
```

Smoke command:

```bash
export ANTHROPIC_API_KEY=...
python -m recipe.gaia_evolver.run \
  --max-tasks 3 \
  --num-rounds 2 \
  --concurrency 1 \
  --max-steps 10 \
  --run-tag smoke_no_gpu
```

Expected artifact shape:

```text
runs/smoke_no_gpu/
├── R0/
│   ├── config.yaml
│   ├── trajectories/
│   └── sessions/
├── R1/
│   ├── config.yaml
│   └── evolve/
└── comparison.json
```

This reproduces the harness-evolution loop. It does not train model weights.

## GPU Boundary

Stop claiming no-GPU progress once the next step requires actual model weight
updates:

- SFT on scrubbed trajectory manifests.
- LoRA / GRPO / PPO through veRL.
- Agentic RL with multi-turn rollout engines.

HarnessX's `verl_harnessX` recipe lists PyTorch CUDA and 8x H100 for full
training. Our local no-GPU work should therefore stop at stable datasets,
verifiers, trajectory scrubbing, memory proxy, and harness-only gates.

## Migration Track For This Repo

The local priority order is:

1. Keep MiniLang as the clean causal proof for K_spec quarantine.
2. Add MiniAPI / ToolWorld as the first agentic environment:
   hidden API constraints, deterministic state verifier, bounded diagnostic
   probes, action-level trajectories.
3. Reuse the same evaluation families:
   headroom, leakage/counterfactual, memory proxy, robust adoption.
4. Only after safe memory reproduces headroom gain should we create trainable
   manifests for SFT / veRL.
5. Use AppWorld / TAU2-Bench after MiniAPI, and Terminal-Bench / GAIA only as
   later external validation.

## Done-When Gates

No-GPU phase is done when:

- MiniLang headroom/leakage/adoption remain reproducible.
- MiniAPI has a deterministic simulator, verifier, and smoke runner.
- MiniAPI records include action traces and process metrics.
- Source-specific plans are caught by counterfactual or robust adoption gates.
- Trainable manifests are still blocked unless scrubbed memory transfers on
  heldout/counterfactual splits.

Current status:

- MiniAPI simulator, memory proxy, and robust adoption smokes are now runnable
  without GPU.
- The shared manifest validator marks rows as trainable only when leakage scan
  passes and robust adoption is `promote_candidate`.
- HarnessX has been cloned and smoke-tested locally; see
  `docs/result/HARNESSX_LOCAL_REPRO_SMOKE.md`.
- Local HarnessX GAIA-style smoke verifies the runner and trajectory filesystem.
  Full reported GAIA gains still need real task data, more API budget, and a
  meta-agent that reliably writes candidate `config.yaml`; model evolution
  still requires GPU.

GPU phase starts only after these gates are met and documented in `docs/result/`.

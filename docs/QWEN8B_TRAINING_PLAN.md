# Qwen 8B Training Plan On 8xA100

## Goal

Use accepted HarnessX/Terminal-Bench 2.1 trajectories to train Qwen 8B without confusing harness-only gains with model-weight gains.

The first server target is LoRA on Qwen 8B. Full fine-tuning is not the default because LoRA is cheaper, easier to roll back, and supports clean adapter ablations.

## Inputs

Only use trajectories from accepted harness configurations:

```text
H* rollout
  -> messages
  -> tool calls
  -> tool outputs
  -> final answer
  -> verifier reward
  -> failure taxonomy
```

Do not train on held-out test trajectories. Do not train on HCAST/METR-HRS by default.

## Stages

### Stage 1: SFT Cold Start

Use successful and near-successful Terminal-Bench 2.1 rollouts from H*.

Training rows should preserve:

- user instruction;
- model reasoning/action messages where allowed;
- tool-call sequence;
- important tool observations;
- final answer or stop signal.

Rows should remove:

- task IDs when they function as memorization keys;
- test set paths not available to the agent;
- verifier internals not visible during normal rollout;
- accidental ground truth or solution snippets.

### Stage 2: GRPO/RL

After SFT cold start, run GRPO or another multi-rollout RL method through HarnessX/Harbor. Reward should start simple:

```text
reward = verifier_pass
       - small_cost_penalty
       - format_or_tool_misuse_penalty
       - infra_failure_penalty
```

Do not optimize against final held-out tasks during RL.

### Stage 3: 2x2 Ablation

Report all four combinations:

| Combination | Meaning |
| --- | --- |
| `H0 + M0` | baseline |
| `H* + M0` | harness-only gain |
| `H0 + M*` | model-only gain |
| `H* + M*` | combined gain |

This is mandatory. Without it, the experiment cannot distinguish a better harness from a better model.

## Server Notes

Expected server:

```text
8xA100
Qwen 8B base model
LoRA adapters
verl/GRPO or SFT pipeline
```

Before using the server, local work must produce:

- fixed Terminal-Bench 2.1 train/dev/held-out split;
- H0 baseline;
- at least one accepted H*;
- trace exporter contract;
- data validation that rejects held-out/test rows.

## Risks

- Sparse reward: use SFT or best-of-N behavioral cloning before RL if pass reward is too rare.
- Harness overfit: freeze H* before training M* and keep held-out untouched.
- Verifier Goodhart: include cost/tool misuse penalties and manual failure review.
- Distribution shift: rerun H0/M* and H*/M*; do not assume the evolved harness remains optimal after model update.

# HarnessX And SIA Flow

## Key Distinction

HarnessX and SIA are not the same layer.

| Layer | HarnessX | SIA |
| --- | --- | --- |
| Role | agent harness substrate / foundry | self-improvement orchestration recipe |
| Main artifact | `HarnessConfig`, processors, tools, memory, sandbox, trajectory | per-generation `target_agent.py`, execution log, improvement note |
| Harness evolution | MetaHarness reads trajectories and writes new config/code | Feedback Agent reads logs and writes next target agent |
| Model evolution | trajectories to SFT/RL/GRPO training records | paper describes weight updates; local quickstart mainly exposes scaffold iteration |
| Best use here | long-term infrastructure and training bridge | design pattern for Meta/Target/Feedback loop |

## HarnessX Loop

HarnessX separates behavior from model binding:

```python
agent = model.agentic(harness)
```

Practical execution flow:

```text
BaseTask
  -> Harness.run(task)
  -> run_loop()
  -> processors assemble context / memory / control
  -> provider.complete()
  -> tool_registry.execute()
  -> EvaluationProcessor / verifier reward
  -> StatefulTrajectory + HarnessResult
```

For Terminal-Bench, the local HarnessX adapter already maps Harbor's container environment into a HarnessX sandbox. The default TB2 harness uses a Bash-only tool set, task time reminders, self-verification, compaction refresh, parse retry, tool-call correction, background install guard, and repeated-edit warning.

## SIA Loop To Borrow

SIA's useful abstraction is the three-role loop:

```text
Meta-Agent
  -> writes or selects initial target agent/scaffold
Target Agent
  -> attempts tasks and logs actions/results
Feedback Agent
  -> analyzes failures and proposes next-generation scaffold or weight update
```

For this project, the safe version is:

```text
HarnessX TB2 rollout
  -> failure taxonomy
  -> Meta/Feedback proposal
  -> edit HarnessConfig or processor
  -> rerun fixed dev split
  -> accept/revert gate
```

Do not let the feedback loop write task-specific hacks into prompts, parsers, regexes, or tool wrappers. The proposal must state the failure class it addresses and why it should transfer beyond one task.

## Four Learning Levels

| Level | Persistent? | Example | Training status |
| --- | --- | --- | --- |
| Test-time adaptation | no | multi-step tool use in one run | not model learning |
| Memory reuse | yes, outside weights | summaries, lessons, failure modes | can help but can leak |
| Harness evolution | yes, program/config | prompt, tool policy, retry, parser, memory | first active loop |
| Model evolution | yes, weights/LoRA | SFT, GRPO, PPO, DPO | server phase |

## Required Ablation

Every serious result must report:

| Combination | Meaning |
| --- | --- |
| `H0 + M0` | baseline harness and baseline model |
| `H* + M0` | harness-only gain |
| `H0 + M*` | model-only gain |
| `H* + M*` | co-evolution or synergy |

Without this 2x2 table, a gain is not attributable.

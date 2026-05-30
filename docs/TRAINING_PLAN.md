# Training Plan: SFT and verl

## Purpose

服务器阶段可以模仿 SIA 自己训模型，但本项目的训练目标不是“让分数最高”，而是验证 quarantine boundary：

> `K_gen` / `theta` 是否能通过 SFT 或 RL internalize 到 weights，同时 `K_spec` 不泄漏进 weights。

训练只在 MiniLang A/B/C 三项 no-training evidence 基本成立后启动。8 张 A100 先用于 LoRA SFT / LoRA GRPO，而不是 full fine-tuning。

## Training Gate

进入训练前必须满足：

1. `k_spec` headroom 稳定。
2. `renamed_vocab`、composition/rule swap、held-out family 能区分 source raw memory 和 target scaffold。
3. raw / stripped / artifact-scrubbed trace dataset 生成稳定。
4. scrubber 能自动拒绝 surface token mapping、当前 rulebook、答案、family-id leakage。
5. Offline adoption score 与 counterfactual removal delta 有可解释相关性。

不满足这些 gate 时，上 SFT/GRPO 只会把泄漏写进 adapter。

## Data Contract

所有训练和评测都应从同一份 manifest 派生：

```json
{
  "run_id": "minilang-trace-v0",
  "base_model": "Qwen-or-DeepSeek-family",
  "env": "MiniLangHard",
  "split": "train|seen_eval|renamed_vocab|rule_swap|heldout_family|no_specific_harness",
  "trace_variant": "raw|stripped|artifact_scrubbed|reward_rollout",
  "episode_id": "episode-7",
  "family_id": "family-7-hard",
  "scaffold_condition": "no_scaffold|k_spec|k_gen|k_spec_k_gen",
  "skill_calls": [],
  "prompt": [],
  "response": "",
  "answers": [],
  "verifier": {},
  "usage": {},
  "leakage_scan": {}
}
```

Required exports：

- JSONL for audit and debugging。
- OpenAI-style chat JSONL for SFT toolchains。
- parquet for verl SFT / GRPO data loaders。
- eval manifest with immutable split ids。

## SFT Track

Purpose：测试 trace abstraction 是否能 internalize 成 `theta`。

Arms：

| Arm | Training data | Expected role |
| --- | --- | --- |
| Base | none | 下限 |
| Raw SFT LoRA | raw successful traces | leakage control |
| Stripped SFT LoRA | stripped traces | 主实验 |
| Artifact-scrubbed SFT LoRA | stricter stripped traces | leakage-safe arm |
| Raw SFT + no-specific eval | raw traces, eval removes K_spec | 测 memorization 依赖 |

SFT success pattern：

- Raw SFT 在 seen-family 可能高，但 renamed / rule-swap / held-out 应更脆。
- Stripped / scrubbed SFT 在 no-specific-harness 和 held-out 上提升。
- Harness Dependence Ratio 下降。

Implementation notes：

- First target：7B/8B instruct model + LoRA rank 32。
- If A100 is 80GB, 14B/32B LoRA is realistic; 70B LoRA requires careful offload and should wait until the protocol is stable。
- Preserve base model, tokenizer, chat template, seed, LoRA rank, learning rate, max length, data manifest hash。
- Do not mix raw and stripped traces in the main adapter unless explicitly running an ablation。

## verl / GRPO Track

Purpose：训练 skill use / creation / adoption policy，而不是先训练 domain facts。

Start only after offline adoption works。

Reward components：

```text
R = task_success
  - cost_penalty(token_cost, tool_calls, verifier_calls)
  - forbidden_action_penalty
  - leakage_penalty(K_spec_use_on_counterfactual)
  + robust_adoption_bonus(counterfactual_removal_delta)
```

GRPO design：

- Group prompts by same episode family and split。
- Sample multiple rollouts per prompt for relative rewards。
- Keep verifier deterministic。
- For MiniLang, tool calls can initially be simulated query/verifier calls。
- For MiniAPI, use actual simulator tool calls and state-based verifier。

verl features to use：

- SFT trainer config for supervised stripped-trace pretraining。
- GRPO for grouped rollout training。
- Agentic RL / multi-turn support for MiniAPI。
- LoRA support to keep 8xA100 training tractable。
- Async rollout once verifier/tool latency matters。

Server baseline config sketch：

```text
hardware: 8 x A100, prefer 80GB if using 32B+ models
model: 7B/8B first, then 14B/32B after protocol stability
adapter: LoRA rank 32 first
rollout: vLLM or SGLang backend through verl
eval cadence: every checkpoint on seen, renamed, rule_swap, heldout, no_specific_harness
checkpoint policy: keep best robust-adoption checkpoint, not best seen-family checkpoint
```

## SIA-like Outer Loop

SIA-like loop for this repo：

1. Run current harness on task distribution。
2. Save full trace, verifier outputs, usage, failure labels。
3. Feedback policy chooses one action:
   - harness update：change prompts/tools/scaffold/skill library；
   - SFT update：train on scrubbed stripped traces；
   - verl update：GRPO on deterministic reward；
   - quarantine update：ban or demote leaking artifact。
4. Evaluate on counterfactual and no-specific-harness splits before promotion。

Promotion rule：

- Harness artifact promotion requires positive removal delta and no counterfactual leakage。
- Weight adapter promotion requires Internalization Gain > 0 and Leakage Susceptibility not worse than base/control。
- Any artifact with seen-only gains is quarantined, even if adoption is high。

## Reporting

Every training run should produce：

- `manifest.json`
- `train_config.yaml`
- `eval_summary.json`
- per-split tables for success / learning cost / leakage
- adapter checkpoint path
- data hash and code commit
- short failure analysis

Main tables for paper：

1. Headroom and learning cost。
2. Raw vs stripped SFT across counterfactuals。
3. Adoption score vs removal delta。
4. SIA-like harness-only vs weights-only vs quarantined weight updates。

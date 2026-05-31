# K_gen Interactive Protocol

This document defines the next MiniLang repair target: turn `K_gen` from static advice or precomputed probes into a bounded current-episode evidence-acquisition protocol.

## Objective

`k_gen_interactive` is not another prompt condition. It is a small harness protocol that lets the model acquire, test, and repair current-episode hypotheses under a fixed budget.

The scientific question is:

> Can general learning procedures reduce MiniLang learning cost without receiving reusable task-specific facts?

This condition sits between two existing arms:

| Arm | Gives model | Role |
| --- | --- | --- |
| `k_gen` | prose discovery playbook | weak general advice baseline |
| `k_gen_exec` | fixed diagnostic observations selected by the harness | evidence scaffold baseline |
| `k_gen_interactive` | executable-probe draft / verify / one-step repair loop | target general procedure |
| `k_spec` | current rulebook | task-specific upper bound |

## Boundary

`k_gen_interactive` must stay inside `K_gen`. It may expose current-episode evidence, but it must not expose reusable `K_spec`.

Allowed:

- consume a bounded number of diagnostic meanings and receive their current commands;
- submit candidate parses or generated commands to a verifier;
- receive coarse verifier feedback such as pass/fail and mismatch field labels;
- revise only failed fields after feedback;
- record all actions and observations as an action trace.

Forbidden:

- reveal the current full rulebook;
- query the exact target of a generation task;
- ask for or reveal final task answers;
- reuse source-world tokens, family identifiers, rulebooks, or previous final answers;
- brute-force generation by unlimited verifier submissions.

If the condition reaches `k_spec`-level accuracy by consuming broad oracle-like evidence, the protocol is too permissive. If it stays close to prose `k_gen`, the action interface is too weak.

## State And Actions

Each run maintains an explicit interaction state:

```text
E_t: current evidence set
H_t: current hypothesis over slots and structure
B_q: remaining query budget
B_v: remaining verifier budget
A_t: action trace
```

The action set should be deliberately small:

| Action | Input | Harness response | Counts as |
| --- | --- | --- | --- |
| `propose_hypothesis` | repair policy and unknowns | acknowledgement | hypothesis step |
| `query_example` | one meaning plus reason | command for that meaning, unless disallowed | query call |
| `verify_candidate` | candidate parse/generation answer batch | pass/fail plus coarse mismatch labels, no answer | verifier call |
| `repair_candidate` | named failed fields plus evidence link | acknowledgement | repair step |
| `final_answer` | final JSON answers plus audit | terminal verification | final attempt |

Recommended coarse verifier labels:

- `wrong_action`
- `wrong_object`
- `wrong_color`
- `wrong_count`
- `wrong_negation`
- `malformed_command`
- `wrong_order_or_morphology`
- `missing_slot`
- `extra_slot`

Do not return the expected command or expected meaning in feedback. The feedback is for repair, not answer disclosure.

## Trace Contract

The interactive trace should be first-class data, not text scraped from a prompt.

Each record should include:

```json
{
  "episode_id": "episode-7",
  "condition": "k_gen_interactive",
  "actions": [
    {"type": "propose_hypothesis", "hypothesis": {}, "unknowns": []},
    {"type": "query_example", "meaning": {}, "reason": "isolate count marker", "observation": "current command"},
    {"type": "verify_candidate", "candidate": {}, "feedback": ["wrong_order_or_morphology"]},
    {"type": "repair_candidate", "repair": {"fields": ["count"], "evidence_ids": [1]}},
    {"type": "final_answer", "audit": {}}
  ],
  "metrics": {
    "accuracy": 0.0,
    "parse_accuracy": 0.0,
    "generate_accuracy": 0.0,
    "query_calls": 0,
    "verifier_calls": 0,
    "repair_count": 0,
    "final_attempts": 0
  },
  "leakage_scan": {}
}
```

For downstream trace abstraction, generate three memory variants:

| Variant | Contents | Expected use |
| --- | --- | --- |
| `raw_action` | current commands, hypotheses, feedback, final answers | leakage control only |
| `action_stripped` | action sequence, reasons, feedback categories, repair pattern; no surface atoms | main memory proxy candidate |
| `artifact_scrubbed_action` | shorter policy template over action types and stop criteria | strict training candidate |

Existing prose `stripped` should remain as a control arm, not the main target.

## Metrics

Report task quality and learning cost together:

- accuracy, parse accuracy, generation accuracy;
- query calls;
- verifier calls;
- repair count;
- final attempts;
- token cost;
- direct target query violations;
- leakage pass rate after stripping.

Useful derived metrics:

```text
query_efficiency = (accuracy(k_gen_interactive) - accuracy(k_gen_exec)) / max(query_calls, 1)
verifier_efficiency = repaired_failures / max(verifier_calls, 1)
harness_gap = accuracy(k_spec) - accuracy(k_gen_interactive)
```

`harness_gap` should remain positive. A zero gap usually means the interactive scaffold leaked too much current rule information.

## Robust Adoption

Naive adoption is still useful as an observation:

```text
adoption_score(s) = call_rate(s) * success_when_called(s)
```

It is not a promotion rule.

Promotion should use split-aware counterfactual removal:

```text
delta(s, split) = success(full_library, split) - success(remove_s, split)
```

Classify skills as:

| Class | Rule |
| --- | --- |
| reusable `K_gen` | leakage scan passes, no target-query violations, and transfer deltas are non-negative within tolerance |
| ephemeral `K_spec` | seen-world delta is positive but counterfactual or heldout delta is negative, or leakage scan fails |
| redundant | all deltas are near zero |
| harmful trap | removal improves counterfactual or heldout performance |

A concrete score can be:

```text
robust_score(s)
  = adoption_score(s)
  * max(0, mean(delta(s, counterfactual_splits + heldout_splits)))
  * cost_efficiency(s)
```

with a hard gate:

```text
min(delta(s, counterfactual_splits + heldout_splits)) >= -epsilon
```

The gate matters more than the scalar score. A high-adoption seen-only skill is `K_spec`, not reusable `K_gen`.

## Experimental Sequence

First rerun headroom:

```text
no_scaffold, k_gen, k_gen_exec, k_gen_interactive, k_spec
```

Then rerun memory proxy:

```text
none,
raw,
prose_stripped,
raw_action,
action_stripped,
artifact_scrubbed_action
```

Then rerun adoption with robust classification:

```text
same_world,
renamed_vocab,
composition_swap,
heldout_family
```

The adoption report should include both naive adoption and robust classification. The expected positive result is not that every generic skill has high score; it is that leaking K_spec no longer gets promoted.

## Success Criteria

The next repair passes if:

1. `k_gen_interactive` beats `k_gen_exec` on hard MiniLang under a fixed budget, or clearly repairs known weak episodes while preserving cost accounting.
2. `k_gen_interactive` remains below `k_spec`, preserving a visible task-specific upper bound.
3. action-stripped traces pass leakage scan and outperform prose stripped traces on heldout or no-specific-harness memory proxy.
4. robust adoption classifies `kspec_source_rulebook` as ephemeral `K_spec` even if naive adoption remains high.

## Kill Conditions

Stop and redesign the protocol if:

1. the model can reach near-`k_spec` performance by querying broad oracle evidence;
2. final answer feedback reveals expected answers or exact corrected commands;
3. query/verifier costs explode while accuracy is flat;
4. action-stripped traces are not better than prose stripped traces;
5. robust adoption still promotes a leaking source rulebook.

# Archived Prior Results: MiniLang / MiniAPI

These results are retained only as methodological guardrails. They are no longer the active project direction.

## What Was Useful

The previous synthetic line established three reusable lessons:

1. Raw traces are dangerous training material because they can contain task-specific facts.
2. Counterfactual and held-out splits are required to distinguish reusable process knowledge from source-specific leakage.
3. Naive adoption/call-rate is not enough; removal delta is a better signal for whether a skill or harness item is causally useful.

These lessons carry into HarnessX/Terminal-Bench as data hygiene and ablation rules.

## Representative Results

### MiniLang Headroom

Early hard-mode runs showed that explicit task rulebooks (`k_spec`) produced large gains over no scaffold. That was useful as infrastructure validation, but it also proved why task-specific rulebooks cannot be blindly distilled into weights.

### MiniLang Leakage

Counterfactual transforms such as renamed vocabulary, order swap, composition swap, and held-out family separated target scaffold recovery from source raw leakage. The important lesson is not the synthetic metric itself; it is the split design.

### MiniAPI Memory Proxy

The strongest old result was the MiniAPI memory/adoption smoke:

| Memory variant | Same-world | Counterfactual | Held-out | Leakage scan |
| --- | ---: | ---: | ---: | --- |
| raw | strong | poor | partial | fail |
| action_stripped | strong | strong | strong | pass |
| artifact_scrubbed_action | strong | strong | strong | pass |
| artifact_scrubbed prose | weak | weak | weak | pass |

Interpretation: source-specific raw memory can help when the world is unchanged, but it does not robustly transfer. Action-level protocols that re-ground through current evidence are safer.

### Robust Adoption

The old robust adoption gate correctly promoted generic API skills:

- `kg_auth_first`
- `kg_probe_hidden_profile`

It quarantined source-specific or harmful skills:

- `kspec_source_profile`
- `trap_skip_receipt`

Most important lesson: a source-profile skill had the highest naive adoption score, but negative counterfactual/held-out removal delta. This is the same failure mode to guard against in Terminal-Bench harness evolution: do not promote a trick just because it helps the dev tasks.

## Status

The code and run artifacts that produced these results were removed from the active tree. If these experiments need to be resurrected, use git history; do not reintroduce them as a parallel active path.

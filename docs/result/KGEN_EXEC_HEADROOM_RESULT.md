# Executable K_gen Headroom Result

This is the factual note for the first no-training repair after Day 4-6.
The goal was to test whether MiniLang was the wrong scenario, or whether the
current `K_gen` scaffold was too weak because it was only prose advice.

## Question

The previous conclusion was:

- `K_gen` is too weak.
- stripped/scrubbed traces have weak positive heldout signals, but are not
  stable enough for SFT.
- adoption score is vulnerable to `K_spec`.

This run isolates the first issue. If executable `K_gen` gives a large
headroom gain while prose `K_gen` does not, then the scene is probably not the
main problem. The system was missing an executable scaffold interface.

## Harness Change

Added a new condition:

- `k_gen_exec`: keeps the old general discovery playbook, then adds an
  executable query-scaffold block.

The executable block simulates a generic MiniLang query planner:

- it requests deterministic diagnostic examples from the current episode;
- it records those requests as `query_calls`;
- it treats the observations as current-episode evidence, not reusable memory;
- it does not reveal the full `K_spec` rulebook;
- it does not query exact generation-task targets.

Also fixed a sampler issue:

- diagnostic examples no longer waste budget on duplicate meanings;
- executable probes are slot-balanced and task-aware, instead of random
  examples from one local cluster.

Code paths:

- `zharness/agents/prompts.py`
- `zharness/eval/run_headroom.py`
- `zharness/envs/minilang/generator.py`

## Expected Result Before Rerun

Expected:

- `k_gen_exec` should be much stronger than prose `k_gen`.
- `k_gen_exec` should still trail `k_spec`, because it receives evidence but
  not the full rulebook.
- `query_calls` should expose the learning-cost tradeoff.
- remaining failures should point to missing verifier feedback or incomplete
  probe coverage.

Kill condition:

- if `k_gen_exec` is close to prose `k_gen`, then MiniLang may be too hard for
  the current one-shot prompt interface, or the query scaffold is not selecting
  useful evidence.

## Run

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -u -m zharness.eval.run_headroom \
  --episodes 4 \
  --difficulty hard \
  --support-budget 4 \
  --parse-tasks 4 \
  --generate-tasks 4 \
  --client openrouter_newapi \
  --model deepseek-v3.2 \
  --api-key-env apihy_API_KEY_deepseek \
  --base-url-env apihy_BASE_URL \
  --reasoning-effort none \
  --conditions no_scaffold,k_gen,k_gen_exec,k_spec \
  --output-dir runs/kgen-exec-headroom-hard-deepseek-v1
```

Artifacts:

- `runs/kgen-exec-headroom-hard-deepseek-v1/records.jsonl`
- `runs/kgen-exec-headroom-hard-deepseek-v1/summary.json`

## Result

| condition | n | accuracy | parse | generate | query calls | verifier calls | tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_scaffold` | 4 | 0.094 | 0.125 | 0.062 | 0 | 0 | 3542 |
| `k_gen` | 4 | 0.062 | 0.125 | 0.000 | 0 | 0 | 4043 |
| `k_gen_exec` | 4 | 0.625 | 0.562 | 0.688 | 32 | 0 | 5628 |
| `k_spec` | 4 | 0.938 | 1.000 | 0.875 | 0 | 0 | 4554 |

Per-episode `k_gen_exec`:

| episode | accuracy | parse | generate | query calls |
| --- | ---: | ---: | ---: | ---: |
| `episode-7` | 0.750 | 0.500 | 1.000 | 8 |
| `episode-8` | 0.500 | 0.500 | 0.500 | 8 |
| `episode-9` | 0.875 | 1.000 | 0.750 | 8 |
| `episode-10` | 0.375 | 0.250 | 0.500 | 8 |

## What This Shows

This strongly supports the diagnosis that the scene is not the main problem.
MiniLang is useful because it reveals the missing mechanism: prose `K_gen`
does not operationalize learning, while executable query evidence does.

The gap is large:

- `k_gen_exec - k_gen`: +0.562 accuracy.
- `k_gen_exec - no_scaffold`: +0.531 accuracy.
- `k_spec - k_gen_exec`: +0.312 accuracy.

So MiniLang has enough headroom, and `K_gen` can help when it is expressed as
actions and observations rather than advice.

## Gap To Expected Result

Matched expectation:

- executable `K_gen` is clearly useful;
- it remains below `K_spec`;
- learning cost is now visible through `query_calls`;
- the result does not require training.

Remaining gap:

- `episode-10` is still weak after the slot-balanced repair;
- `verifier_calls` are still zero;
- this is not yet a real multi-step active learner;
- it gives extra observations in one prompt, rather than letting the agent
  hypothesize, query, verify, repair, and stop.

Likely reason:

- static probes can expose many slots, but they do not catch wrong intermediate
  hypotheses;
- generation remains vulnerable to agreement/count mistakes;
- parse tasks can contain concepts not covered by generation-task-aware probes.

## Updated Conclusion

Do not abandon MiniLang. The scenario is doing its job: it separates three
things that were previously conflated.

1. `K_spec` oracle is still the ceiling.
2. prose `K_gen` is not an adequate scaffold.
3. executable `K_gen` produces a large no-training gain, but still needs
   verifier feedback to become a defensible learning-cost protocol.

This moves the MiniLang v0 protocol from roughly 60-70% complete to about
70-75% complete. It does not move the full Skill-Native / co-evolve system much
yet; that remains around 30-35% because there is still no SFT, no verl/GRPO,
no skill creation, no delayed reward, and no cross-domain transfer.

## Next Repair

The next no-training step should not be more prose. It should add a real
action trace:

```text
hypothesis -> query -> verifier feedback -> repair -> final audit
```

Concretely:

1. add a MiniLang query/verifier runner that allows bounded multi-step probing;
2. record `attempts_to_success`, `query_calls`, `verifier_calls`, token cost,
   and final accuracy;
3. convert stripped traces into action traces from successful runs;
4. rerun Day 5 memory proxy with executable/action stripped traces;
5. rerun Day 6 adoption using robust adoption:
   counterfactual and heldout removal delta must be non-negative before a
   skill can be promoted or distilled.

Only after this passes should the project export SFT/verl manifests.

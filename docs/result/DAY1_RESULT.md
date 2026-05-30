# Day 1 Result: MiniLang Scaffold Headroom

This file is a factual daily result archive. Protocol and future schedule live in `../EXPERIMENT_PLAN.md`; durable model/environment decisions live in `../MODEL_AND_ENV_REVISIONS.md`.

## Basic GPT Smoke

Run artifacts:

- Main sweep: `runs/api-day1-8/`
- Rerun for one transient empty-response cell: `runs/api-day1-rerun-episode11/`

Configuration:

- model/client: `gpt_sub2api` / `gpt-5.4`
- episodes: 8
- tasks per episode: 4 parse + 4 generate
- support examples: 12
- conditions: `no_scaffold`, `k_spec`, `k_gen`, `k_spec_k_gen`

Corrected summary after rerunning the transient `episode-11 k_spec_k_gen` empty response:

| condition | accuracy | parse accuracy | generation accuracy | notes |
| --- | ---: | ---: | ---: | --- |
| no_scaffold | 0.781 | 0.688 | 0.875 | Baseline already non-trivial because 12 examples expose many concepts. |
| k_spec | 1.000 | 1.000 | 1.000 | Current rulebook gives full headroom. |
| k_gen | 0.766 | 0.719 | 0.813 | Generic playbook alone is not reliably useful yet. |
| k_spec_k_gen | 1.000 | 1.000 | 1.000 | Matches K_spec ceiling after rerun. |

Initial insight:

1. The environment has scaffold headroom: K_spec closes the gap immediately.
2. Parse is harder than generation in this setup; metrics must stay split.
3. K_gen playbook is too weak or too redundant with the examples; Day 2 should make active queries / verifier calls explicit instead of only prompt advice.
4. API gateway can occasionally return empty content; the runner now retries each cell once by default.

Revision after model/environment critique:

- Treat this table as infrastructure validation only.
- Do not use GPT-family models for the main v0 sweeps.
- Use `--difficulty hard` and apihy `deepseek-v3.2` as the current daily sweep default.
- See `../MODEL_AND_ENV_REVISIONS.md` for the current model and environment policy.

Next discriminating check:

- Add counterfactual transforms: `renamed_vocab`, `order_swap`, and later hidden rule permutation.
- Compare source raw rulebook vs target scaffold under those transforms.
- If raw source remains strong after renaming, the task leaks; if it collapses and target scaffold recovers, the measurement protocol is useful.

## Hard-Mode DeepSeek Sweep

Combined from:

- `runs/hard-deepseek-v3_2-smoke2/`
- `runs/hard-deepseek-v3_2-extra6/`

Configuration:

- model/client: `openrouter_newapi` / `deepseek-v3.2`
- API route: apihy
- difficulty: `hard`
- seeds: 7-14
- episodes: 8
- support examples: 8
- tasks per episode: 4 parse + 4 generate

| condition | n | accuracy | parse | generate |
| --- | ---: | ---: | ---: | ---: |
| no_scaffold | 8 | 0.250 | 0.219 | 0.281 |
| k_spec | 8 | 0.969 | 1.000 | 0.938 |
| k_gen | 8 | 0.234 | 0.219 | 0.250 |
| k_spec_k_gen | 8 | 1.000 | 1.000 | 1.000 |

Interpretation:

1. Hard mode has real scaffold headroom.
2. `K_spec` is a strong oracle and should remain the headroom upper bound.
3. Current `K_gen` is not an effective scaffold; it is neutral or harmful.
4. The next valid `K_gen` must be executable/interactive: query selection, verifier calls, counterexample construction, and repair, not only prose.

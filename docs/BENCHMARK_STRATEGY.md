# Benchmark Strategy

截至 2026-06-02，本项目采用分层 benchmark 策略。不要把所有 benchmark 都放进同一个 inner optimization loop。

| Benchmark | Role | Use For Harness Evolution | Use For Model Training | Main Risk |
| --- | --- | ---: | ---: | --- |
| Terminal-Bench 2.1 | primary loop | high | medium-high | environment flakiness, verifier mismatch, long wall time |
| Terminal-Bench 2.0 | historical smoke only | low | no | old-version drift |
| τ³-bench text domains | second-stage text transfer | medium | low initially | domain-specific interaction protocols mistaken for general harness |
| WebArena | cross-domain browser validation | medium-high | low initially | browser state fragility, sparse reward |
| BALROG | long-horizon pressure test | medium | medium later | game-specific policies mistaken for general harness |
| HCAST | external autonomy calibration | low | no by default | anti-training / held-out contamination |
| METR-HRS | reporting layer | no | no | expensive human-time calibrated protocol |

## Primary Choice: Terminal-Bench 2.1

Terminal-Bench 2.1 matches HarnessX's strengths:

- long-horizon terminal workflow;
- Docker/container state;
- bash/file-system operations;
- tests/verifier reward;
- realistic failure modes: timeout, dependency setup, background service, output file mismatch, parser/tool-call failures.

The project pins paper-facing work to:

```text
terminal-bench/terminal-bench-2-1
```

Terminal-Bench 2.0 is now only a historical migration smoke. It should not appear as the primary result table unless the paper explicitly frames a version comparison.

## Secondary Validation

τ³-bench text domains should be the next text-agent transfer check after Terminal-Bench 2.1 H0/H* are stable. Its purpose is to test whether the evolved harness transfers beyond terminal tasks while staying closer to text/tool interaction than browser or game environments.

WebArena should be introduced only after Terminal-Bench H0 and at least one H* are stable. Its purpose is to answer: did the evolved harness learn general agent control patterns, or only terminal-specific command habits?

BALROG should be used after WebArena for long-horizon planning/exploration stress. It is not the first training source because stochastic/game-specific shortcuts are easy to overfit.

HCAST and METR-HRS should remain final calibration. They are valuable precisely because they are expensive, human-calibrated, and not repeatedly optimized during development.

## Reporting Rule

Every benchmark table must include:

- benchmark version or commit;
- task split and task count;
- model and harness config ID;
- sandbox backend;
- number of repeats;
- pass rate/reward;
- cost, latency, token/tool-call count when available;
- infrastructure error count separate from verifier failure.

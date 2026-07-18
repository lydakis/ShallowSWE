# Protocol Governance

ShallowSWE separates methodology, execution, analysis, and experiment planning so a roadmap label
cannot change benchmark behavior.

## Authority Order

When active documents conflict, use this order:

1. `docs/white-paper-v0.4.2.md` defines the frozen normative methodology.
2. `docs/protocol-governance.md` defines software and document boundaries.
3. `docs/weekend-six-task-kaggle-goal-2026-07-18.md` is the sole current execution plan.
4. `docs/verifier-contract.md` and `docs/task-quality-audit.md` define task-local functional QA.
5. `docs/kaggle-runner.md` and `docs/pier-integration.md` define backend operations.

`docs/future/` is not active. `docs/archive/` is provenance only. DeepSWE support documents and
files under `paper/` remain frozen and do not control ShallowSWE execution. The complete inventory
is `docs/README.md`.

The white paper and papers change only after concrete evidence and explicit owner approval.

## Software Boundaries

```text
Experiment plan -> RunSpec + TaskBundle -> harness -> ResultBundle
ResultBundle + MethodologySpec -> analyzer -> AnalysisBundle
```

The harness enforces only execution facts:

- exact task, verifier, environment, model, agent, seed, and price identities;
- verifier-submission, agent-step, dollar, wall-time, batch, and retry limits;
- one persistent conversation and filesystem per repair loop;
- verifier and credential isolation with no model fallback;
- event-level usage, cost, verifier, and artifact capture; and
- requested-versus-resolved model checks.

The harness does not interpret experiment phase, canary status, readiness, funding, review status,
evidence class, release class, or publication eligibility. A run unit may carry opaque
`run_metadata`; execution never branches on it.

The analyzer applies an explicit `MethodologySpec` after execution. It may select rows, compute
metrics, propose caps and task budgets, or apply fallback rules. An analysis artifact is never
execution authority by itself.

Experiment plans decide which run specs to create and when to proceed. Those decisions live in
versioned configuration and planning documents, not in runner code.

## Runner Roles

| Runner | Role |
|---|---|
| Local deterministic execution and Docker | Task QA, isolation, and controller conformance. |
| Kaggle | Primary funded benchmark execution. |
| Pier/Harbor | Local portability and reproducibility. |
| Codex subscription | Optional development transport with separate provenance. |
| OpenRouter | Optional external comparator with separate provenance. |

Rows can be pooled only when canonical model identity, agent policy, task contract, continuation,
limits, and sampling controls match. Backend provenance remains mandatory. Known fallback,
unresolved identity, incompatible scaffolds, or different continuation semantics remain separate.

## Freeze Boundary

Before metered execution, one `RunSpec` and generated task bundle must freeze task hashes, requested
and expected resolved model identities, agent policy, exact seed matrix, safety limits, and price
basis. A model, task, or seed outside that spec fails closed. A mismatch produces excluded rows and
a new versioned run spec rather than a silent substitution.

## Private Real-Case Boundary

The public six-task shakedown uses original fixtures to validate pipeline machinery. The private
corpus preserves real transcript-mined work for later held-out calibration. Historical source
trajectories are discovery evidence only. Fresh frozen runs establish calibration and scoring
claims, with source provenance retained as a contamination threat marker.

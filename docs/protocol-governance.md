# Protocol Governance

ShallowSWE separates normative methodology from implementation history so a stale command or
preview convention cannot silently change the benchmark.

## Normative Order

When documents conflict, use this order:

1. `docs/white-paper-v0.4.2.md` defines the metric, estimands, task construct, calibration phases,
   bounded repair loop, claim tiers, and release policy.
2. `docs/six-task-pilot-protocol-v0.3.md` freezes the six-task protocol-validation pilot,
   trajectory allocation, temporary limits, budget gates, and stage transitions.
3. `docs/verifier-contract.md` and `docs/task-quality-audit.md` define task-local functional QA.
4. `docs/kaggle-runner.md` and `docs/pier-integration.md` define backend-specific implementation
   and operations, subject to the shared protocol above.
5. `SPEC.md`, `docs/methodology.md`, `docs/calibration-protocol.md`, and `docs/pilot-plan.md` retain
   implementation history. Their category-by-size and fixed-preview-cap language is superseded for
   v0.4.2 calibration and must not launch official rows.

Any semantic change to items 1 or 2 increments the document version and invalidates later official
rows that depend on the changed rule. Editorial clarifications that do not change scoring or
selection semantics are recorded without reusing a frozen run manifest.

## Runner Roles

| Runner or surface | Role | Evidence class |
|---|---|---|
| Local deterministic execution | Task QA, isolation, schema, and controller conformance | Non-model QA |
| Docker | Fresh network-disabled task-quality probes | Non-model QA |
| Codex subscription | Development triage and defect discovery | Development only |
| Kaggle | Canonical funded six-task pilot | Official metered pilot evidence |
| Pier/Harbor | Portability, local reproduction, and backend parity | Eligible model evidence under the shared contract |
| OpenRouter | Optional preregistered external comparator | Separate optional evidence |

Kaggle and Pier consume the same canonical task packet and shared repair-loop contract. Rows are
presumptively equivalent across those backends when canonical model identity, agent policy, task,
prompt, tool protocol, continuation behavior, limits, and sampling controls match. Runner or
gateway differences alone do not prevent pooling. Known model fallback, unresolved model identity,
materially different behavior, or an incompatible scaffold or continuation contract does.

Backend provenance is mandatory even when rows are pooled. Every model row records `runner`,
`runner_version`, `inference_gateway`, and `provider_route`; requested and resolved model identity
remain attached. Published aggregates disclose every contributing runner and route so backend
effects can be audited or stratified without redefining the headline model result.

## Freeze Boundary

Before any official canary row:

- task, verifier, environment, price sheet, requested model configuration, provider route,
  sampling configuration, agent policy, runner version, and pilot manifest are hashed and frozen;
- provider fallback is disabled;
- the exact evidence class is recorded;
- the batch passes its stage and cumulative budget preflight.

The canary validates resolved model identity, continuation, isolation, usage, and charge
reconciliation. It cannot select a different requested configuration after observing outcomes. A
mismatch produces excluded rows and a new versioned manifest.

## Private Real-Case Boundary

The public six-task pilot validates protocol machinery using original fixtures. The private corpus
preserves real transcript-mined repository work for later held-out calibration. Historical source
trajectories are discovery evidence only. Fresh frozen runs establish all calibration and scoring
claims, and source-model/session provenance remains attached as a contamination threat marker.

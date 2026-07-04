# ShallowSWE Task Selection Rubric

This document is the selection gate for official ShallowSWE task candidates. It answers one question:

```text
Does this kind of work belong in ShallowSWE?
```

Use `docs/verifier-contract.md` for the separate question of whether a candidate is judged correctly.

## Benchmark Shape

ShallowSWE measures the cost of routine software work delegated to coding agents. A task should look like a work packet an orchestrator could hand to a subagent with a concrete expected outcome.

The benchmark has one weighted task surface with tiered difficulty:

- **T1-T3 price index**: the official shallow-work basket. These tasks should remain close to saturation for the accepted floor model so CPSC measures routine-work efficiency.
- **T4 shelf edge**: an opt-in crossover tier. These tasks stay routine in kind, but add enough sequencing and edge cases that weaker or lower-effort models may fail. T4 locates the point where a more capable or higher-effort row becomes cheaper overall.

Do not make T1-T3 harder just to force low-effort failures. Keep T1-T3 calibrated to the shallow price-index promise, and use T4 for the crossover question.

## Inclusion Rule

A task belongs when all of these are true:

- A working engineer would recognize it as normal maintenance or delegation work.
- The desired outcome is behaviorally clear before seeing any reference solution.
- The task can be completed offline in a deterministic Pier environment.
- Complexity comes from touch points, sequencing, and state, not cleverness.
- The verifier can test observable outcomes without requiring the reference implementation.
- The prompt can be written like a real ticket: brief, concrete, and not over-explanatory.

A task does not belong when any of these are true:

- It is a puzzle, interview question, algorithm challenge, or standalone function exercise.
- Correctness depends on taste, product judgment, hidden knowledge, current events, or external services.
- The only reliable grader is a human reading the patch.
- The task requires insight rather than diligence.
- It is copied from a public issue, PR, benchmark, tutorial, or known exercise.
- The verifier must assert implementation shape not stated in the prompt.

## Categories

Each task has exactly one primary category.

### Fix

Correct a defect or regression in existing behavior.

Good examples:

- A documented input path crashes on an edge case.
- A duplicate import is counted twice.
- A config alias is parsed but ignored downstream.

Selection risks:

- Too many Fix tasks make the benchmark a bugfix suite only.
- Single-function fixes are useful for smoke tests but weak benchmark evidence unless project context matters.

### Transform

Convert, join, normalize, or summarize local artifacts into a fixed output schema.

Good examples:

- Join invoices, payments, refunds, and customers into payouts and rejects.
- Migrate records through a documented schema version.
- Parse logs into canonical rows plus malformed-line rejects.

Selection risks:

- If all rules are in one visible mapping table, the task may become clerical.
- If rules are underspecified, the verifier becomes arbitrary.

### Operate

Perform multi-step maintenance in a repo or local workflow.

Good examples:

- Trace a config value through env, loader, service, and CLI.
- Rename a concept across code, fixtures, docs, and compatibility aliases.
- Move or split modules while preserving public imports.

Selection risks:

- Git/worktree tasks must have deterministic expected state.
- Avoid chores that are mostly formatting, unless they expose meaningful repo orientation cost.

### Invoke

Use a deterministic local mock API or tool surface to reach a final state.

Good examples:

- Find an existing ticket and update it instead of creating a duplicate.
- Reconcile a local manifest against API-side state.
- Follow a documented retry path after a deterministic transient error.

Selection risks:

- The API must be local and fully deterministic.
- Call count is usually diagnostic, not pass/fail. Use pass/fail only for final state and destructive overreach.

Invoke is load-bearing for ShallowSWE's positioning: as work gets decomposed into subagent-sized units, this category measures the cost of delegated tool/API action.

## Complexity Bands

Initial tier labels are authoring hypotheses. Calibration data decides the final tier.

Tier calibration uses a versioned panel of 2-3 inexpensive anchor rows, not a single control model.
This avoids overfitting tier labels to one model's quirks and gives the suite a reproducible ruler.
Calibration runs are quarantined from published leaderboard stats; published snapshots use fresh
rollouts and flag anchor rows when they are included.

| Tier | Purpose | Expected surface | Calibration gate |
| --- | --- | --- | --- |
| T1 | Sanity and cheap calibration | 1-3 files, obvious local behavior | Calibration-panel median near 100% |
| T2 | Main routine-work band | 4-8 files, one small behavior change | Calibration-panel median >=90% |
| T3 | Saturated shallow edge | 8-20 files, multiple touch points | Calibration-panel median 80-95% |
| T4 | Shelf edge crossover | Routine work with longer chains, more edge cases, or more state | Calibration-panel median 30-70% and top row >=80% |

T4 is part of the same price index once accepted. It should still be labeled by tier so users can
understand where failures start affecting CPSC.

Use coarse bands only. Distinguishing 95% from 85% requires enough rollouts that small-N results
should be treated as sizing evidence, not tier assignment. Spend high-N calibration on cheap anchor
rows before running expensive publish panels.

The ladder measures two different mechanisms:

- T1-T2 isolate flailing under saturation: models usually pass, but spend different turns, tokens,
  and dollars.
- T3 introduces the first retry-tax pressure while staying mostly inside the shallow price-index
  promise.
- T4 is the shelf edge where failures should appear often enough to expose capability/cost
  crossovers.

## Complexity Levers

Allowed levers:

- More files that must be touched or inspected.
- More layers between symptom and cause.
- More edge cases stated by prompt or fixtures.
- More local state to reconcile.
- More sequential steps where later work depends on earlier output.
- More regressions to preserve.
- More deterministic API/tool calls.

Disallowed levers:

- Ambiguous requirements.
- Hidden product preferences.
- Obscure algorithms.
- External package or API knowledge not documented in the repo.
- Public benchmark/task content.
- Verifiers that demand a specific implementation style.

## Source Policy

Public repositories and benchmarks are sampling frames, not task content.

Allowed:

- Count recurring issue shapes.
- Study patch size, file count, and touched subsystems.
- Record abstract patterns.
- Keep source URLs in a private authoring log when needed for audit.
- Use natural issue phrasing as style inspiration.

Disallowed:

- Copy issue text.
- Copy tests.
- Copy patches.
- Reuse exact filenames, identifiers, fixtures, or domain data that make the source recoverable.
- Lift tasks from saturated benchmarks such as HumanEval, MBPP, or SWE-bench.

Every task should record contamination notes, even when the source pattern is only abstract.
Public benchmark artifacts should not publish issue URLs. They invite later authors to copy from
the source and add little value after the task has been rewritten from scratch.

## Candidate Pattern Card

Before authoring an instance, write a short pattern card:

```toml
category = "invoke"
tier_hypothesis = "t3"
maintenance_type = "corrective"
shape = "reconcile-states"
delegated_work_unit = "reconcile a service manifest against ticket API state"
expected_touchpoints = 6
expected_engineer_minutes = 35
verifier_shape = "mock API final state plus destructive-overreach checks"
source_pattern = "manifest/API reconciliation with idempotent updates"
copied_text = false
copied_patch = false
copied_tests = false
contamination_notes = "source used only for abstract workflow shape"
```

`expected_engineer_minutes` is an authoring heuristic unless a task-specific note explains how it
was estimated. Do not publish it as a measured benchmark field.

Do not create a Pier task until the pattern card has a plausible verifier shape.

## Acceptance Gates

A candidate can enter calibration only after these gates pass:

1. **Realism**: the task reads like normal work.
2. **Prompt clarity**: reviewers agree on the expected outcome from the prompt alone.
3. **Verifier feasibility**: the behavior can be judged programmatically.
4. **Reference independence**: the verifier accepts two materially different correct solutions.
5. **Contamination control**: source pattern notes are present and no content was copied.
6. **Environment reliability**: the base project and verifier run offline and deterministically.
7. **Pre-registered calibration**: the card states expected pass-rate bands and the predicted
   cheapest-correct row class before any model run.

Official admission requires verifier validation, human review, and calibration as defined in `docs/verifier-contract.md` and `docs/task-sourcing-methodology.md`.

## Next Slice

Do not fill the full matrix next. First add tasks that test the missing and uncertain dimensions:

| Task slot | Suggested shape | Why |
| --- | --- | --- |
| Invoke T2 | `update-dont-duplicate` | Adds the missing category with a realistic idempotency workflow |
| Invoke T3 | `reconcile-states` | Tests delegated API/tool action with more state |
| Fix T4 | `parallel-fix` or `regression-from-diff` | Finds whether higher capability beats low effort on multi-site repair |
| Operate T4 | `cross-cutting-rename` or `merge-divergent-branches` | Tests sequencing and repo-state discipline |
| Transform T4 | `schema-upgrade-pipeline` plus rejects | Tests longer deterministic transformation chains |

The goal of this slice is not a publishable headline. It is to see whether the CPSC curves bend with complexity and whether the verifier contract is strong enough before scaling the suite.

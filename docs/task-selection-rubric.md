# ShallowSWE Task Selection Rubric

This document is the selection gate for official ShallowSWE task candidates. It answers one question:

```text
Does this kind of work belong in ShallowSWE?
```

Use `docs/verifier-contract.md` for the separate question of whether a candidate is judged correctly.

## Benchmark Shape

ShallowSWE measures the cost of routine software work delegated to coding agents. A task should look like a work packet an orchestrator could hand to a subagent with a concrete expected outcome.

The benchmark has one weighted task surface with two public axes:

- **Category**: code, artifact, or workflow.
- **Size**: small, medium, or large.

Do not make tasks harder just to force low-effort failures. The benchmark should model realistic
company workload mixes, then let repair-loop solve rate, verifier submissions, turns, tokens, and
CPSC reveal where the economical up-front model choice changes.

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

### Code

Change code behavior.

Good examples:

- A documented input path crashes on an edge case.
- A duplicate import is counted twice.
- A regression test needs to be added before a fix.
- A small feature needs CLI, serializer, or API wiring.
- A new status or enum needs to behave consistently across code surfaces.

Selection risks:

- Too many Code tasks make the benchmark a bugfix suite only.
- Single-function fixes are useful for smoke tests but weak benchmark evidence unless project context matters.

### Artifact

Convert, join, normalize, or summarize local artifacts into a fixed output schema.

Good examples:

- Join invoices, payments, refunds, and customers into payouts and rejects.
- Migrate records through a documented schema version.
- Parse logs into canonical rows plus malformed-line rejects.

Selection risks:

- If all rules are in one visible mapping table, the task may become clerical.
- If rules are underspecified, the verifier becomes arbitrary.

### Workflow

Perform multi-step maintenance in a repo, local workflow, or deterministic tool/API surface.

Good examples:

- Trace a config value through env, loader, service, and CLI.
- Rename a concept across code, fixtures, docs, and compatibility aliases.
- Move or split modules while preserving public imports.
- Find an existing ticket and update it instead of creating a duplicate.
- Reconcile a local manifest against API-side state.
- Follow a documented retry path after a deterministic transient error.

Selection risks:

- Git/worktree tasks must have deterministic expected state.
- The API must be local and fully deterministic.
- Call count is usually diagnostic, not pass/fail. Use pass/fail only for final state and destructive overreach.
- Avoid chores that are mostly formatting, unless they expose meaningful repo orientation cost.

Workflow is load-bearing for ShallowSWE's positioning: as work gets decomposed into subagent-sized units, this category measures the cost of delegated repo, tool, and API action.

## Size Bands

Initial size labels are authoring hypotheses. Calibration data can move a task up or down.

Size calibration uses the protocol in `docs/calibration-protocol.md`. Author labels are hypotheses;
the final size is assigned by cheap first-submit behavior after the task clears the pre-registered
ceiling one-shot gate. Published snapshots use fresh repair-loop seeds for scoring.

| Size | Purpose | Expected surface | Floor one-shot diagnostic |
| --- | --- | --- | --- |
| Small | Sanity and high-volume delegated work | 1-3 files, obvious local behavior | 70-100% |
| Medium | Main routine-work band | 4-8 files, one routine behavior change | 30-70% |
| Large | Bigger sub-agent work packets | 8-20 files, more state or sequencing | 0-40% |

Use coarse bands only. Small-N results should be treated as plumbing or sizing hints, not final
assignment. Spend high-N repair-loop calibration on the selected floor and ceiling before running
expensive publish panels.

The size axis measures two different mechanisms:

- Small isolates flailing under saturation: most rows pass, but spend different turns and dollars.
- Medium is the routine delegation band where cheap rows may begin losing reliability.
- Large introduces convergence pressure while staying inside realistic delegated work. It should
  straddle the reliability-cost break-even zone for the selected floor or it is not doing useful
  work.

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
category = "workflow"
size_hypothesis = "large"
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
7. **Pre-registered calibration**: the card states expected one-shot calibration bands and the
   predicted cheapest-correct row class before any model run.

Official admission requires verifier validation, human review, and calibration as defined in `docs/verifier-contract.md` and `docs/task-sourcing-methodology.md`.

## Next Slice

The 36-task scaffold is authored. The next slice is calibration and reshaping, not filling slots:

- Run the floor-selection sweep and choose the floor by measured dynamic range.
- Run the pinned ceiling and selected floor at calibration N.
- Move or reshape tasks that miss their measured size band.
- Add context-heavy large tasks only if the large band remains too fixture-small to expose
  reliability-cost crossover behavior.

The goal is to make the CPSC denominator earn its place while keeping every task shallow enough for
the ceiling to pass.

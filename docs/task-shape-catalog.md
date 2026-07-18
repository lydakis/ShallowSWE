# ShallowSWE Task Shape Catalog v0.2

The durable object of the benchmark. Tasks are instances; shapes are reusable work patterns.
Each snapshot may rotate freshly authored tasks from these shapes; cost comparability holds at the
category-size-shape level.

Repo note: task instances use Pier's flat local task layout under `tasks/<task-id>/`. Public
taxonomy fields live in `[metadata]` as `category` and `size`. Fine-grained authoring detail lives
in `shape`, `subtype`, `family`, and `maintenance_type`.

Every shape must satisfy three invariants when instantiated:

1. **Realism**: reads like a normal work packet someone would hand to an engineer or sub-agent.
2. **Programmatic verifier**: tests behavior, not implementation. No model judges in the scoring path.
3. **Calibration**: repair-loop solve rate, turns, verifier submissions, cap hits, tokens,
   measured cost, and CPSC are measured under the frozen methodology before a task is
   accepted into a snapshot.

Complexity means more touch points, state, sequencing, or regression surface. It never means hidden
insight, obscure algorithms, subjective judgment, or external knowledge.

Per-cell target: 4 tasks instantiated for v1 from the public 3x3 matrix:

```text
3 categories x 3 sizes x 4 tasks = 36 tasks
```

## Code

Change code behavior: bug fixes, tests, features, refactors, and API/CLI/UI behavior. Verifier:
unit tests, command checks, public API checks, and regression guards.

### Small

- `missing-null-guard`: function crashes on empty input; make the provided edge-case test pass.
- `wrong-comparison`: `<` vs `<=`, `is` vs `==`, inverted boolean; symptom described in instruction.
- `regression-test-plus-fix`: add a focused failing test for a local bug, then fix the behavior.
- `exception-handling`: a predictable error escapes; instruction specifies the fallback behavior.

### Medium

- `small-feature-wiring`: add a CLI flag, endpoint, export format, or option across existing layers.
- `fix-failing-test-suite`: 2-3 related tests fail from one root cause; find and fix it.
- `debug-misleading-symptom`: error surfaces in one layer but originates in another.
- `split-module-preserve-api`: split or move code while keeping public imports and behavior stable.

### Large

- `parallel-fix`: the same defect pattern appears in several places; verifier covers hidden surfaces.
- `status-parity`: add a new enum/status consistently across import, API, repair, help, and reports.
- `regression-from-diff`: a recent multi-file change broke behavior; repair the culprit without
  reverting unrelated work.
- `implement-cross-surface-feature`: feature touches several code surfaces and existing behavior must
  remain stable.

## Artifact

Turn inputs into outputs: data files, reports, migrations, summaries, docs-to-structured-output, and
fixed-schema generation. Verifier: schema validation, canonicalized output comparison, aggregate
checks, and reject/error-row checks where relevant.

### Small

- `env-to-json`: convert a `.env`, `ini`, or small CSV file to a specified structured format.
- `extract-fields`: pull specified fields from a messy JSON blob into a flat CSV.
- `strip-and-sort`: deduplicate and sort a list file per stated rules.
- `doc-to-checklist`: read a short markdown spec and produce a structured checklist or JSON summary.

### Medium

- `log-to-schema`: parse a mixed-format log file into structured rows; malformed lines go to rejects.
- `report-summarize-fixed`: reduce a data file to a summary with exact specified aggregates.
- `markdown-table-restructure`: reshape tabular markdown into a different specified layout.
- `multi-source-join-with-rejects`: merge several files on shared keys with stated reject reasons.

### Large

- `schema-upgrade-pipeline`: migrate mixed-version inputs into a canonical output package.
- `report-from-many`: produce one summary report from several heterogeneous input files.
- `dirty-data-normalize-at-scale`: canonicalize thousands of rows with enumerated edge-case rules.
- `ledger-or-reconciliation-package`: emit multiple output files, rejects, and summary totals.

## Workflow

Operate on repo, tool, or system state: config chains, git operations, deterministic mock APIs,
tickets, local deployment-like chores, and idempotent reconciliation. Verifier: repo state, command
output, mock API final state, call logs, and destructive-overreach checks.

### Small

- `rename-symbol`: rename one function across a few files including imports and call sites.
- `move-file-fix-imports`: relocate a module and repair references.
- `cut-ticket`: turn a short bug report into one well-formed local mock ticket.
- `single-lookup-act`: query a local mock API for one record, then act on the answer.

### Medium

- `config-chain`: change a value that flows through env, loader, config object, and consumer.
- `branch-cherry-pick`: create a branch, cherry-pick a specified commit, and resolve a trivial conflict.
- `dependency-bump-fix`: upgrade one pinned dependency available offline and repair one renamed API.
- `update-dont-duplicate`: find an existing mock ticket and update it instead of creating a duplicate.

### Large

- `cross-cutting-rename`: rename a config or domain concept across code, fixtures, docs, and help.
- `feature-branch-workflow`: choose and apply a small set of commits under deterministic criteria.
- `merge-divergent-branches`: merge a branch and resolve several conflicts derivable from tests/docs.
- `reconcile-states`: converge a local manifest against deterministic API-side state without deletes.
- `error-and-recover`: follow a documented retry path after a deterministic transient API failure.

## Instantiation Rules

1. Write every instance from scratch. Take no content from GitHub issues, existing benchmarks,
   tutorial sites, or interview-question repositories.
2. Vary surface details across instances of the same shape: language, domain flavor, naming, and
   file layout.
3. Keep work shallow: small <= 3 files, medium <= 8 files, large <= 20 files unless the extra files
   are fixtures or generated outputs. Large earns its size through touch points, not deep code.
4. Reference solution first, verifier second, instruction last. Instruction states the goal and
   constraints like a real ticket: brief, concrete, no implementation hints.
5. Every environment is fully offline: vendor dependencies into the image, mock APIs served
   in-container.
6. Acceptance pipeline per instance: verifier fails the base for the intended reason, passes the
   reference solution three clean times, passes a materially different alternate solution, then
   passes human prompt-verifier review and calibration.

## Review Checklist

- Would a working engineer recognize this as a real task?
- Does the verifier pass any correct solution, including ones structured differently from the oracle?
- Is there exactly one reasonable interpretation of the instruction?
- Is the task solvable with diligence rather than cleverness?
- Does every hidden assertion trace back to the prompt or existing repo behavior?

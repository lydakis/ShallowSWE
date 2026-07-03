# ShallowSWE Task Shape Catalog v0.1

The durable object of the benchmark. Tasks are instances; shapes are the spec. Each snapshot may rotate in freshly instantiated tasks from these shapes; cost comparability holds at the shape level.

Repo note: task instances use Pier's flat local task layout under `tasks/<task-id>/`; category, tier, and shape should live in `[metadata]`.

Every shape must satisfy three invariants when instantiated:

1. **Saturation**: floor model passes >=80% across rollouts, or the instance is simplified or cut.
2. **Programmatic verifier**: tests behavior, not implementation. Runs twice against the oracle during acceptance to catch flakiness.
3. **Realism**: reads like a Tuesday-afternoon task someone hands an agent, not a puzzle.

Tier calibration is empirical and two-directional. T3 means: as complex as possible while the floor model still clears the gate. During gating, about 60% floor pass rate means simplify; all floor candidates at 100% with low turn counts on a T3 instance means escalate the shape. The gate finds the tier's true level.

Complexity boundary: complexity means more steps, more files, more sequencing, never cleverness. The moment a task requires insight rather than diligence, it belongs to DeepSWE and leaves this suite, even if the floor model happens to pass it.

Per-cell target: 3 tasks instantiated for v1 from any of the listed shapes. 4 categories x 3 tiers x 3 tasks = 36.

## Fix

Deterministic coding. Single clear defect or gap, one obviously correct behavior. Verifier: unit tests.

### T1

- `off-by-one`: a loop or slice bound is wrong; one failing test provided, make it pass.
- `wrong-comparison`: `<` vs `<=`, `is` vs `==`, inverted boolean; symptom described in instruction.
- `missing-null-guard`: function crashes on empty input; make the provided edge-case test pass.
- `typo-identifier`: misspelled variable/function name breaks the module; error message given.

### T2

- `implement-to-spec`: docstring and test suite exist, function body is `pass`; implement it. Example: `normalize-username`, though the existing seed task should not automatically count toward the pilot.
- `fix-failing-test-suite`: 2-3 related tests fail from one root cause; find and fix it.
- `edge-case-patch`: function works on happy path, fails on documented edge cases; provided tests cover them.
- `exception-handling`: function lets a predictable error escape; instruction specifies the desired fallback behavior.

### T3

- `implement-small-feature`: add a real feature such as a new endpoint, CLI subcommand, or export format touching 3-4 files, against provided acceptance tests. Diligence-heavy: wiring, registration, plumbing, no design decisions.
- `debug-misleading-symptom`: error surfaces in one layer but originates in another. Stack trace is visible; cause requires tracing.
- `regression-from-diff`: a recent multi-file change visible in git log broke behavior; identify the culprit hunk and correct it without reverting unrelated parts of the same commit.
- `parallel-fix`: the same defect pattern was copied into 3-4 places; failing tests cover two, instruction requires fixing all occurrences, and verifier tests the untested ones too.

## Transform

Extraction and reshaping. Input artifact in, output artifact out, fixed target schema. No editorializing. Verifier: exact or canonicalized output comparison.

### T1

- `env-to-json`: convert a `.env` file to JSON, or `ini` to `toml`, or `csv` to `jsonl`.
- `extract-fields`: pull specified fields from a messy JSON blob into a flat CSV.
- `strip-and-sort`: deduplicate and sort a list file per stated rules.

### T2

- `log-to-schema`: parse a mixed-format log file into structured rows matching a given schema; malformed lines go to a rejects file.
- `config-migration`: translate a config between formats where keys are renamed per a provided mapping table.
- `report-summarize-fixed`: reduce a data file to a summary with exact specified aggregates in a fixed output format.
- `markdown-table-restructure`: reshape tabular data embedded in markdown into a different specified layout.

### T3

- `multi-source-join-with-rejects`: merge three files on shared keys with stated conflict-resolution rules; unmatched and malformed records route to separate reject files with reason codes.
- `schema-upgrade-pipeline`: migrate records v1 to v3 through two documented schema versions where fields split, merge, and derive; intermediate v2 output is also verified.
- `dirty-data-normalize-at-scale`: canonicalize a few thousand rows of inconsistent data to a fixed standard; edge-case rules are enumerated, verifier checks aggregate counts plus sampled rows.
- `report-from-many`: produce one summary report from 5-6 heterogeneous input files with overlapping keys; exact aggregates and layout are specified.

## Operate

Multi-step work in a repo. Requires orientation and sequenced actions across files or git state. Verifier: repo end-state checks.

### T1

- `rename-symbol`: rename one function across 2-3 files including imports and call sites; tests verify.
- `move-file-fix-imports`: relocate a module to a new package path and repair references.
- `gitignore-and-untrack`: add patterns to `.gitignore` and remove already-tracked matching files from the index.

### T2

- `config-chain`: change a value that flows through a chain such as env var to config loader to consumer; tests assert the end-to-end effect.
- `branch-cherry-pick`: create a branch, cherry-pick a specified commit onto it, resolve the trivial conflict it causes.
- `dependency-bump-fix`: upgrade one pinned dependency available offline in the image and fix the one renamed API call it breaks.
- `split-module`: split one oversized file into two modules along an indicated seam, keeping the public interface stable.

### T3

- `feature-branch-workflow`: branch from a specified commit, cherry-pick two of four candidate commits per stated criteria, resolve the resulting conflict, ensure tests pass, and leave the repo on the correct branch.
- `cross-cutting-rename`: rename a concept across function names, config keys, CLI flags, docs, and test fixtures, with a deprecation shim for the old CLI flag per instruction.
- `trace-and-fix-config-bug`: symptom is given; cause is a config indirection three or four hops away, with one red-herring config that plausibly looks responsible.
- `restructure-package`: reorganize a flat module into the documented target package layout, repair imports, and keep the public API surface and tests green.
- `merge-divergent-branches`: merge a branch that diverged by several commits, resolving 4-5 conflicts spanning code and config where correct resolutions are derivable from tests and comments.

## Invoke

Tool-call precision. Agent gets a small tool set: file ops plus a task-specific mock API served locally in the container. Goal is achievable in a known minimum number of calls. Verifier checks mock API recorded state and call log, asserting outcome state with call count as a diagnostic, not a pass condition.

### T1

- `cut-ticket`: turn a short bug report into one well-formed ticket via the ticket API.
- `single-lookup-act`: query the mock API for one record, then act on the answer.
- `post-status`: read a result file, post a correctly formatted status update via the API.

### T2

- `triage-batch`: given 5 bug reports, file tickets with correct severity and labels per a rubric; duplicates are filed once and linked.
- `lookup-join-act`: answer requires combining two API queries, such as finding the owner of a failing service and assigning the ticket.
- `update-dont-duplicate`: a ticket for the issue already exists; correct behavior is finding and updating it, not filing a new one.

### T3

- `dependent-chain-long`: six-to-eight-step workflow where each API call's input derives from previous outputs, including one branch point resolved via an extra lookup.
- `reconcile-states`: diff a local manifest against API-side state across about 20 records and issue exactly the calls needed to converge. Verifier checks final state and flags destructive overreach.
- `error-and-recover`: mid-chain endpoint returns a documented transient error on first call; correct behavior is the documented retry, then completion. Mock is deterministic and fails exactly once.
- `bulk-triage-with-lookup`: triage 8-10 bug reports into tickets where severity depends on data fetched per report; includes two duplicates to link and one invalid report to close per rubric.

## Instantiation Rules

1. Write every instance from scratch. Take no content from GitHub issues, existing benchmarks, tutorial sites, or interview-question repositories. Shapes above are the only seed.
2. Vary surface details across instances of the same shape: language, domain flavor, naming, and file sizes.
3. Keep repos small: T1 <= 3 files, T2 <= 8 files, T3 <= 20 files. Shallow means shallow: T3 earns its size through touch points, never through code that must be understood deeply.
4. Reference solution first, verifier second, instruction last. Instruction states the goal and constraints the way a colleague would in a ticket: brief, concrete, no hints about implementation.
5. Every environment is fully offline: vendor dependencies into the image, mock APIs served in-container.
6. Acceptance pipeline per instance: verifier runs twice against oracle, floor-candidate gate >=80%, human review, then merge.

## Review Checklist

- Would a working engineer recognize this as a real task?
- Does the verifier pass any correct solution, including ones structured differently from the oracle?
- Is there exactly one reasonable interpretation of the instruction?
- Is the task solvable with zero cleverness?

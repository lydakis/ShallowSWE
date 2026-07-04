# ShallowSWE Task Sourcing Methodology

ShallowSWE should not treat the current `py-normalize-username` task as benchmark evidence. It is a harness smoke task. Official benchmark tasks need to be realistic, project-shaped, and shallow enough to measure routine-work efficiency rather than frontier capability.

This document defines how to source, author, review, and calibrate official ShallowSWE tasks.

Use this document as the end-to-end authoring pipeline. Use `docs/task-selection-rubric.md` as the entry gate for which work packets belong in the suite, and `docs/verifier-contract.md` as the pass/fail contract for task verifiers.

## Benchmark Lessons

### SWE-bench

SWE-bench builds tasks from real GitHub issue and pull-request pairs. Each task gives the agent an issue description plus the codebase before the human fix. Evaluation uses fail-to-pass tests that fail before the PR and pass after it, plus pass-to-pass tests for regressions.

Source: https://www.swebench.com/original.html

What to copy:

- Real repository context matters.
- Fail-to-pass plus pass-to-pass style grading is a useful verifier shape.
- Issue-resolution tasks are more realistic than standalone function puzzles.

What to avoid:

- Public PR-derived fixes are contamination-prone.
- Historical issue text can be ambiguous, underspecified, or inconsistent with tests.
- Tests derived from a human PR can be too narrow, rejecting behaviorally correct alternate fixes.

### SWE-bench Lite

SWE-bench Lite narrows the original benchmark for cheaper iteration. Its selection removes instances with images, external links, explicit commit/PR references, short problem statements, more than one edited file, more than three edit hunks, file creation/deletion, and fragile error-message checks.

Source: https://www.swebench.com/lite.html

What to copy:

- Explicit filtering criteria are better than vibes.
- Development subsets should be cheaper and faster than official snapshots.
- Patch statistics such as files, hunks, and line counts are useful difficulty metadata.

What to avoid:

- The Lite constraints are too narrow for ShallowSWE's official suite. We do want multi-file shallow work, config chains, data pipelines, and simple feature wiring.

### SWE-bench Verified

SWE-bench Verified adds human review for issue clarity, test correctness, and solvability. OpenAI's writeup also documents the original failure modes: overly specific tests, underspecified problem statements, and environment instability.

Sources:

- https://www.swebench.com/verified.html
- https://openai.com/index/introducing-swe-bench-verified/
- https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/

What to copy:

- Every official task needs independent human review.
- Review should check prompt clarity, verifier alignment, solvability, and environment reliability.
- Difficulty should be annotated by expected experienced-engineer effort, not only by patch size.

What to avoid:

- Human filtering after the fact is not enough if the task source itself is contaminated or tests are copied from public PRs.
- Static public task sets age badly. ShallowSWE should version snapshots and rotate newly authored tasks.

### SWE-bench Live

SWE-bench Live keeps the issue-resolution formulation but uses recent GitHub issues and an automated curation pipeline. Its initial Python release reports 1,319 tasks from 93 repositories, with freshness as an explicit contamination control. It records repository and patch statistics, fail-to-pass and pass-to-pass counts, and plans regular updates.

Sources:

- https://arxiv.org/html/2505.23419v1
- https://github.com/microsoft/SWE-bench-Live

What to copy:

- Use GitHub as a pattern sampler and freshness signal.
- Record repository domain, file count, LOC, patch files, hunks, and lines as task metadata.
- Automate candidate discovery and environment validation where possible.

What to avoid:

- Fully automated issue/PR task creation optimizes scale, not necessarily verifier fairness.
- Real issue/PR tasks are not ideal for an official ShallowSWE test set because the fixes are public.

### SWE-smith

SWE-smith creates synthetic software-engineering training tasks from Python codebases by constructing execution environments, synthesizing bug instances, keeping tasks that break existing tests, and generating issue text.

Sources:

- https://arxiv.org/abs/2504.21798
- https://github.com/SWE-bench/SWE-smith

What to copy:

- Programmatic mutation/synthesis is useful for generating candidate tasks at scale.
- Existing test suites can help validate that a task actually changes behavior.
- Synthetic task generators can produce many candidates for calibration and training.

What to avoid:

- Synthetic breakage can feel artificial unless filtered by human review.
- ShallowSWE official tasks should not be opaque mutations. They should read like normal work a developer would hand to an agent.

### DeepSWE

DeepSWE's key move is to use active real open-source repositories as the substrate, but write original tasks, reference solutions, prompts, and behavioral verifiers from scratch. Its public writeup emphasizes broad repository coverage, original tasks, behavioral verification, and review by task authors. The public repo also documents the Harbor/Pier-compatible layout and the separate verifier environment.

Sources:

- https://deepswe.datacurve.ai/blog/deepswe
- https://github.com/datacurve-ai/deep-swe

What to copy:

- Real repos, original tasks.
- Short maintainer-style prompts that describe behavior, not edit steps.
- Reference solution is for offline review, not grading.
- Verifiers should test observable behavior rather than exact implementation structure.
- Prompt-verifier bijection: the verifier tests exactly the behavior requested by the prompt.
- Acceptance breadth: materially different correct implementations should pass.
- Use the standard Pier-compatible task layout.

What to adapt:

- DeepSWE aims at long-horizon frontier tasks. ShallowSWE should target routine maintenance work with lower expected engineer time and lower patch size.
- DeepSWE reports long-horizon coverage. ShallowSWE should emphasize bug localization, test-writing, small feature wiring, config/data work, and repo operations.

### Other Useful References

SWE-rebench, BugsInPy, SWE-bench Multilingual, CodeClash, and SWE-Lancer are useful references, but not direct templates.

What to copy:

- SWE-rebench-style freshness and standardized scaffold reporting.
- BugsInPy-style reproducible real-bug workflows.
- SWE-bench Multilingual's warning that single-language benchmarks invite overfitting.
- CodeClash's reminder that software work ultimately serves goals, even when ShallowSWE should stay task-oriented.
- SWE-Lancer's economic framing: cost matters when the task resembles real paid work.

What to avoid:

- Goal-oriented open-ended competition for v1. That belongs outside ShallowSWE's routine-task scope.
- Pure freelance-task scoring where human subjective judgment is needed.

Sources:

- https://arxiv.org/html/2505.20411
- https://github.com/soarsmu/bugsinpy
- https://www.swebench.com/multilingual.html
- https://codeclash.ai/insights/20251103_release/
- https://openai.com/index/swe-lancer/

## ShallowSWE Official Task Definition

An official ShallowSWE task is:

- grounded in a realistic repository/workflow pattern,
- authored from scratch,
- shallow enough for a floor model to pass at least 80% after calibration,
- project-shaped enough to require orientation,
- classifiable as routine maintenance work,
- verified by behavior, not implementation shape,
- reviewed by at least two humans or review passes,
- runnable offline in a reproducible Pier task environment.

T4 shelf-edge tasks are still routine in kind and must meet the same prompt, contamination, and
verifier standards. They are gated from the top instead of the floor, but once accepted they enter
the same price-index basket as T1-T3.

An official task is not:

- a copied GitHub issue,
- a copied PR fix,
- a standalone coding puzzle,
- a hidden-knowledge task,
- a task whose only path is matching the reference implementation,
- a task whose correctness depends on non-determinism, network access, current time, or provider-specific behavior.

## Source Strategy

Use public GitHub and existing benchmarks as a sampling frame, not as task content.

Allowed source uses:

- Count common issue/PR patterns by repository domain.
- Extract abstract task shapes such as "config value ignored", "CLI option not wired", "parser rejects blank field", "test missing for regression", "schema migration forgot one field".
- Study patch statistics to calibrate files, hunks, and line-count bands.
- Study issue phrasing to make prompts natural.
- Study test failure modes to avoid brittle verifiers.
- Keep source URLs in a private authoring log when they are needed for audit.

Disallowed source uses:

- Copying issue text.
- Copying a patch.
- Copying tests.
- Reusing exact filenames, domain data, or identifiers from a public issue when that would make the original task recoverable by search.
- Publishing public issue URLs in benchmark task files or candidate cards.

Each task should record a `source_pattern` note, for example:

```toml
[metadata.source]
type = "github_pattern"
pattern = "config flag defined but not consumed"
copied_text = false
copied_patch = false
copied_tests = false
```

Public task artifacts should keep the abstract pattern and contamination notes, not the source URLs.
The URL log is an authoring/audit artifact, not benchmark content.

## Maintenance Types

ShallowSWE should use a routine-maintenance taxonomy rather than an "easy/hard coding" taxonomy. Each task should map to one primary maintenance type:

- `corrective`: fix a defect in existing behavior.
- `adaptive`: update code for a dependency, schema, config, platform, or API change.
- `perfective`: add a small user-facing capability, output format, flag, or endpoint.
- `preventive`: improve maintainability without changing public behavior, such as a safe rename, module move, test coverage, typing, or lint cleanup.

These types cut across the UI-facing category labels. For example, a config migration is often adaptive; regression-test-plus-fix is corrective plus preventive; a CLI export format is perfective.

## Task Families

### Bug Localization

The prompt describes a concrete symptom. The fix is small, but the edited file is not named. The repository has enough structure that the agent must inspect tests, config, or call sites.

Examples:

- A CLI summary ignores refunds.
- A parser accepts blank IDs in one import path but not another.
- A service option is documented but unused.

Verifier:

- Fail-to-pass behavior check for the symptom.
- Pass-to-pass regression checks for adjacent behavior.

### Regression Test Plus Fix

The task explicitly asks for a regression test and a bug fix. The verifier checks behavior and checks that a meaningful test file changed.

Examples:

- Add coverage for a duplicate invoice import and fix the dedupe bug.
- Add a CLI regression test for `--json` output and fix serialization.

Verifier:

- Behavior passes.
- A test file in the expected package changed.
- The new test fails against the buggy base when applied without the fix, when practical.

### Small Feature Wiring

The task adds a small feature across existing layers without requiring product design.

Examples:

- Add `--format json` to a report command.
- Add a `status=archived` filter to a local API and CLI.
- Add a config option with documented default behavior.

Verifier:

- API/CLI behavior tests.
- Regression tests for existing flags/routes.
- Public help/docs snapshot if relevant.

### Data Transform

The agent reads local artifacts and writes a fixed output schema.

Examples:

- Join invoices, payments, and refunds into a payout report.
- Migrate config records from v1 to v3 with rejects.
- Summarize logs into exact aggregate rows.

Verifier:

- Canonicalized output comparison.
- Reject-file checks with reason codes.
- Aggregate count checks plus sampled row checks.

### Repo Operation

The task is normal maintenance in a small repo: rename, move, split, config-chain repair, branch operation.

Examples:

- Rename a concept across config, code, fixtures, and docs while preserving an old alias.
- Move a module and repair imports.
- Split an oversized module while keeping the public API stable.

Verifier:

- Test suite.
- Import/API compatibility checks.
- Git/worktree state checks when the task is explicitly operational.

### Dependency/API Adaptation

The task updates code after a dependency, SDK, schema, or internal API shift. It is shallow only when the desired replacement behavior is documented and the affected surface is small.

Examples:

- Update one dependency call after a pinned version bump.
- Migrate a config key from v1 to v2 while preserving the old key as a fallback.
- Replace a deprecated helper with the new package API.

Verifier:

- Existing behavior remains stable.
- New API/config path works.
- Old fallback behavior passes when required by the prompt.

### Quality Hygiene

The task is preventive maintenance with behavior-preserving checks.

Examples:

- Remove stale linter exceptions and fix the underlying issue.
- Add missing type annotations or import hygiene without changing runtime behavior.
- Move duplicated fixtures into a shared helper while keeping tests green.

Verifier:

- Test suite and lint/type checks.
- Public API compatibility checks.
- No generated or unrelated files changed.

### Tool/API Workflow

The agent interacts with a deterministic local mock API.

Examples:

- Deduplicate and update existing tickets.
- Reconcile a local manifest against API state.
- Retry a documented transient error exactly once.

Verifier:

- Final mock API state.
- Call log diagnostics for duplicate/destructive actions.
- Outcome is pass/fail; call count is reported as efficiency metadata unless overreach is destructive.

## Difficulty Bands

ShallowSWE tiers should be calibrated by observed behavior on a versioned cheap calibration panel,
but initial authoring needs bands. Do not define tiers by one control model; use the median or
agreement across 2-3 anchor rows so a single model quirk does not decide difficulty.
The current anchor manifest is `panels/shallowswe-calibration-v0.1.json`.

### T1

- 1-3 files in the repository.
- Reference patch: usually 1 file, <= 2 hunks, <= 25 changed lines.
- Expected experienced-engineer time: 5-10 minutes.
- Prompt can name the failing area.
- Purpose: sanity check and cheap calibration, but still project-shaped.
- Calibration-panel target: median pass rate near 100%. This is still useful because saturated
  tasks isolate flailing, turns, context rent, and cost among successful rollouts.

### T2

- 4-8 files in the repository.
- Reference patch: 1-3 files, <= 5 hunks, <= 80 changed lines.
- Expected experienced-engineer time: 10-25 minutes.
- Prompt describes symptom or desired behavior, not the exact edit.
- Purpose: main ShallowSWE routine-work band.
- Calibration-panel target: median pass rate >=90%. This should remain mostly saturated so the
  price index measures efficiency rather than failure variance.

### T3

- 8-20 files in the repository.
- Reference patch: 2-5 files, <= 10 hunks, <= 180 changed lines.
- Expected experienced-engineer time: 25-60 minutes.
- Requires multiple touch points, but no deep design or clever inference.
- Purpose: expose flailing tax and the first retry-tax effects while staying below DeepSWE-style
  long-horizon work.
- Calibration-panel target: median pass rate 80-95%.

### T4

- Routine work with longer chains, more edge cases, or more local state.
- Top-gated instead of floor-gated.
- Purpose: find the shelf edge where a stronger row can become cheaper overall because failures
  enter the cost-per-success denominator.
- Calibration-panel target: median pass rate 30-70%.
- Top-row target: strongest/top-gated row passes >=80%.

## Metadata

Every official task should carry:

- `category`: fix, transform, operate, or invoke.
- `maintenance_type`: corrective, adaptive, perfective, preventive.
- `tier`: t1, t2, t3, or t4.
- `source_pattern`: abstract source pattern.
- `contamination_notes`.
- `repo_origin`: synthetic_project, small_original_repo, public_repo_snapshot, or forked_public_repo_snapshot.
- `language`.
- `ecosystem`.
- `domain`: cli, web_api, config, data_pipeline, package_library, tool_api, docs_tests, etc.
- `expected_engineer_minutes`.
- `repo_size_band`.
- `files_total`.
- `files_expected_touched_band`.
- `loc_expected_band`.
- `touchpoint_count`.
- `reference_patch_files`.
- `reference_patch_hunks`.
- `reference_patch_lines_added`.
- `reference_patch_lines_deleted`.
- `verifier_type`.
- `visible_tests`: true or false.
- `hidden_tests`: true or false.
- `requires_test_authoring`: true or false.
- `fail_to_pass_tests`.
- `pass_to_pass_tests`.
- `mock_api_call_min`.
- `mock_api_call_max`.
- `ambiguity_score`.
- `internet_required`: false unless explicitly justified.
- `external_knowledge_required`: false.
- `calibration_status`.
- `floor_model_pass_rate`.
- `floor_model_rollouts`.
- `median_turns`.
- `median_tokens`.
- `flakiness_runs`.
- `review_status`.

`expected_engineer_minutes` is an authoring heuristic unless the task defines a repeatable estimate
method. Do not present it as a measured result.

## Authoring Pipeline

1. **Pattern mining**
   - Sample GitHub issues/PRs, SWE-bench metadata, SWE-bench Live metadata, and internal examples only for abstract patterns.
   - Produce a candidate pattern card: symptom, project surface, expected touch points, verifier idea, contamination notes.

2. **Task design**
   - Create an original small project or repository snapshot.
   - Check the candidate against `docs/task-selection-rubric.md`.
   - Write a brief natural prompt.
   - Write the reference solution.
   - Record patch statistics.

3. **Verifier design**
   - Check the verifier against `docs/verifier-contract.md`.
   - Write fail-to-pass behavior tests from the prompt.
   - Write pass-to-pass regression tests.
   - Add hidden tests for acceptable alternate solutions.
   - Avoid checking private symbol names unless the prompt explicitly requires that public API.

4. **Oracle validation**
   - Run the verifier three times against the unmodified base and confirm the intended fail-to-pass tests fail for the right reason while pass-to-pass tests pass.
   - Apply the reference solution and run the verifier three times, clean container each time.
   - Confirm reports are deterministic.

5. **Alternate-solution validation**
   - Have at least one reviewer or baseline agent produce a non-reference solution.
   - Prefer a deliberately different structure or helper decomposition from the reference patch.
   - If a plausible correct solution fails hidden tests, broaden the verifier or reject the task.
   - Add edge/property-style tests where they clarify behavior without adding hidden requirements.

6. **Human review**
   - Reviewer A checks realism and prompt clarity.
   - Reviewer B checks verifier breadth and implementation independence.
   - Score prompt specificity, verifier scope, behavioral coverage, environment reliability, and realism from 0-3.
   - Any score of 2 or 3 blocks acceptance until fixed.

7. **Floor calibration**
   - Run the current versioned calibration panel at enough rollouts for coarse bands, usually N >= 15 on cheap anchor rows.
   - Accept T1-T3 only inside the target calibration band for the hypothesized tier.
   - If all floor candidates pass 100% with low turns, escalate complexity.
   - If failures are ambiguity or verifier mismatch, rewrite. If failures are legitimate flailing, keep.
   - Quarantine calibration rollouts from published leaderboard results.

8. **T4 calibration**
   - Pre-register expected pass-rate bands and the predicted cheapest-correct row class.
   - Run the current versioned calibration panel and the top-gated model class.
   - Accept as T4 only if the calibration-panel median is 30-70%, the top-gated class passes
     >= 80%, and scored rows show meaningful pass-rate or cost-efficiency divergence.
   - Demote to T3 or keep as a probe if every row passes at saturation.

9. **Snapshot admission**
   - Freeze task version, source pattern notes, metadata, and reference patch stats.
   - Add to the workload basket only after calibration and review.

## Review Rubric

Score each item 0-3.

- 0: clean.
- 1: minor concern, acceptable after note or small fix.
- 2: material concern, reject until fixed.
- 3: severe concern, quarantine or redesign.

- Prompt describes user-visible behavior, not implementation hints.
- A working engineer would recognize the task as normal work.
- The task can be solved without external knowledge.
- There is one reasonable interpretation of success.
- The verifier accepts materially different correct implementations.
- Hidden tests do not require behavior absent from the prompt.
- Public API/name checks are only used when the prompt makes that API/name part of the contract.
- Base environment fails for the intended reason.
- Reference solution passes three clean verifier runs.
- At least one regression check guards against collateral breakage.
- Patch size matches the intended tier.
- Source pattern is documented without copying issue text, tests, or patches.

## Verifier Red Flags

Reject or rewrite a task if any of these are true:

- Test imports a helper introduced only by the reference patch.
- Test requires a class, function, file, or internal name not mentioned in the prompt or existing public API.
- Test asserts exact warning/error text when the prompt only asks for behavior.
- Test checks implementation shape instead of observable result.
- Prompt says "fix this" with no repro, example, expected output, or acceptance behavior.
- Reference patch includes unrelated cleanup or broad refactor.
- Base repo cannot run cleanly before the task patch.
- Any test depends on wall clock, randomness, network, filesystem ordering, locale, CPU count, or external service.
- Candidate valid solution fails hidden tests for reasons not inferable from the prompt.
- Task source, issue, PR, or reference patch is public and old enough to plausibly be in training data.
- Reviewers disagree on what a correct fix should do.

## Immediate Plan

Do not fill the full 36-task matrix yet. First author a quality gate pack:

1. `invoice-cli-regression-test-fix`
   - Family: regression test plus fix.
   - Tier: T2.
   - Surface: Python package with CLI, parser, fixtures, tests.
   - Task: add a regression test for duplicate invoice imports and fix dedupe.

2. `report-json-format`
   - Family: small feature wiring.
   - Tier: T2/T3.
   - Surface: CLI, serializer, docs/help, fixtures.
   - Task: add `--format json` to an existing report command.

3. `config-flag-ignored`
   - Family: bug localization / repo operation.
   - Tier: T3.
   - Surface: env file, config loader, service, tests, docs.
   - Task: documented flag is set but ignored at runtime; trace and fix while preserving fallback behavior.

4. `payout-reconcile`
   - Family: data transform.
   - Tier: T3.
   - Surface: local CSV/JSON inputs, rejects file, exact output schema.
   - Task: join invoices, payments, refunds, and customers into a payout report with rejects.

Run the cheap panel at N=3 on this pack. Use the outcomes to decide the floor model and adjust task complexity before writing the remaining suite.

Then add shelf-edge work to the same task set after calibration:

1. `status-terminal-parity`
   - Family: multi-entry status parity fix.
   - Tier hypothesis: T4 signal.
   - Status: authored with reference and alternate solutions; N=1 cheap-anchor sweep saturated.
   - Decision: not accepted as T4 without redesign. Keep as flailing/probe evidence.

2. `config-key-rollover`
   - Family: cross-cutting config rollover.
   - Tier hypothesis: T4 probe.
   - Status: authored with reference and alternate solutions; N=1 expanded-panel sweep saturated.
   - Decision: not accepted as T4 without redesign.

3. `ledger-schema-upgrade`
   - Family: schema-upgrade pipeline with rejects.
   - Tier hypothesis: T4 signal.
   - Status: authored with reference and alternate solutions; N=15 cheap-panel calibration complete.
   - Decision: demoted to calibrated T3. Anchor pass rates were 0.800, 0.867, and 0.933, with
     median 0.867, so the task fails the T4 median band and fits the T3 band.

4. `ticket-state-reconcile`
   - Family: local mock API reconciliation.
   - Tier hypothesis: T4 signal.
   - Status: authored with reference and alternate solutions; N=15 cheap-panel calibration and
     N=5 top-gate calibration complete.
   - Decision: accepted T4. Anchor pass rates were 0.333, 0.400, and 0.667, with median 0.400.
     GPT-5.5 medium passed 5/5 as the top-gated row.

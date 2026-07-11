# ShallowSWE — Specification v0.1

A benchmark for routine software work. Admitted tasks are intended to be within reach of current
frontier agents; cheaper or lower-effort models may fail as tasks get larger. The score is cost per
verified success, not raw accuracy.

ShallowSWE is an independent benchmark inspired by DeepSWE's rigor. It is not affiliated with DeepSWE, Datacurve, Harbor, or Pier.

## Thesis

Most real-world LLM usage is routine: small bugfixes, formatting, extraction, git operations, short
agentic chains. Existing benchmarks measure capability at the frontier and say little about which
model is *economical* for everyday work. ShallowSWE pins a frontier ceiling, dials task size by a
floor-probe panel, and reports cost per successful completion by task category, size, and
`model_config`. The headline output is a single-model reliability-cost frontier: for this workload
basket, under this price sheet, and above a declared solve-rate floor, which single model
configuration is the cheapest verified choice.

Name is a deliberate foil to DeepSWE. Same rigor, opposite end of the pool.

## Core metric

Final ShallowSWE measures a bounded repair loop, not one-shot success and not fresh independent
retries. For each task/model_config/seed row, the agent starts in a clean sandbox, works normally,
declares done, and then the hidden verifier runs. If verification fails, the harness gives limited
non-oracle feedback and the same agent continues in the same context. The loop stops at the first
pass or when a cap is hit.

**Cost per successful completion (CPSC)**, per task and model configuration:

```text
CPSC = total model spend across scored repair-loop rows / number of successful repair loops
```

Failed verifier submissions, extra turns, and final cap-hit failures all count in the numerator.
A cheap model that needs five verifier submissions pays for five submissions. A model that burns the
cap and never passes contributes spend but no success. If an aggregation cell has zero successful
repair loops, CPSC is undefined and displayed as "no verified successes"; its failed-loop spend
remains visible. CPSC is computed per `model_config`; no scored row combines spend from multiple
models.

### Single-model run invariant

Every scored run is bound to exactly one `model_config`, defined as
`(model, effort, sampling_config)`. All agent turns, repair-loop continuations,
verifier-feedback responses, and cap outcomes within that row use the same `model_config`.
ShallowSWE does not use model fallback, escalation, ensembling, judge models, retrying with a
different model, or transcript handoff to another model inside a scored run. If the model fails,
hits a cap, or exhausts context after meaningful work starts, that row records the failure for the
same `model_config`.

Report alongside CPSC:
- **Solve rate**: successful repair loops divided by scored repair loops.
- **Conditional spend among solved loops**: spend among loops that eventually passed, excluding
  failed loops.
- **Verifier submissions to success**: how many hidden-verifier submissions successful loops needed.
- **Cap-hit rate**: dollar, verifier-submission, or agent-step cap hits per scored repair loop.
- **Token diagnostics**: raw input, output, cache, and reasoning tokens across the full loop. Token
  counts are durable within a model family, but cross-model comparisons use measured dollars from a
  versioned price sheet.

Wall time is an infra guard, not a scored differentiator. A wall-time stop is classified as infra
and retried unless the step cap also corroborates a genuine model loop.

## Run modes

ShallowSWE has two run modes:

1. **One-shot calibration mode**
   - Start from a clean sandbox.
   - Let the agent work normally and declare done once.
   - Run the hidden verifier once.
   - Do not continue after verifier failure.
   - Use this for task admission, ceiling gate checks, floor selection, and size calibration.
   - Do not use this as the final CPSC leaderboard.

2. **Bounded repair-loop scoring mode**
   - Start from a clean sandbox.
   - Let the agent work normally and declare done.
   - Run the hidden verifier.
   - On failure, give only allowed coarse feedback and continue in the same context.
   - Stop at first pass or cap.
   - Use this for final published CPSC.

## Calibration Panels

Each snapshot has two pre-registered calibration panels:

- `ceiling_panel`: frontier `model_config`s used only to decide whether a candidate task is
  admissible for the snapshot.
- `floor_probe_panel`: cheaper or lower-effort `model_config`s used to assign task size.

The ceiling and floor-probe panels are frozen before suite authoring and task admission. The
broader published leaderboard panel may be frozen later, before the full published repair-loop run.

For v1, the primary ceiling row is `ceiling_gpt_5_5_xhigh` in
`panels/shallowswe-ceiling-v0.1.json`, reported as `openai/gpt-5.5[extra_high]`. Medium-effort
rows are smoke evidence only and do not satisfy admission. A candidate task is admitted if at
least one pre-registered `ceiling_panel` config achieves `>=75%` one-shot success over `N=16`
attempts and verifier review finds no task flaw. For v1, that means at least `12/16` successful
one-shot runs.

Size is assigned from the primary floor-probe configuration selected from
`panels/shallowswe-calibration-v0.1.json`. Secondary floor-probe configs are recorded for
sensitivity analysis and trigger manual review if they disagree with the primary assignment by more
than one size band.

## Task suite

The durable suite design lives at the shape level. See `docs/task-shape-catalog.md` for the current catalog used to instantiate original tasks.

### Categories

Three categories. Each answers "which single model configuration is economical for this kind of
work?"

1. **Code** — change code behavior: bug fixes, regression tests, small features, refactors, API compatibility, and UI or CLI behavior.
2. **Artifact** — turn inputs into outputs: data joins, reports, migrations, summaries, docs-to-structured-output, and fixed-schema file generation.
3. **Workflow** — operate on repo, tool, or system state: config chains, git operations, local mock APIs, tickets, deployment-like chores, and idempotent state reconciliation.

### Sizes

Three sizes per category. Sizes turn each crossover from a point into a curve: "Model X is cheaper for small code work, but another model wins once workflow chunks get large."

- **Small** — one clear local change or output. Usually 1-3 touched files.
- **Medium** — one routine delegated chunk with a few touch points. Usually 4-8 touched or inspected files.
- **Large** — a larger but still routine sub-agent work packet with more state, sequencing, or regression surface. Usually 8-20 touched or inspected files.

Size is assigned by calibration outcome, not by author estimate. File-count ranges are authoring
heuristics only.

- v1 target: 3 categories × 3 sizes × 4 tasks = **36 tasks**.
- Published leaderboard panel: versioned `model_config` rows with rollout counts set by the claim.
  Keep every broad run behind a budget preflight; publish snapshots rerun when the panel or task
  version changes.
- v1 single-model eligibility floor: **90% scored repair-loop solve rate**. If no row in a
  category/size slice reaches the floor, the site displays "no recommended configuration" for that
  slice and shows the cheapest rows within two percentage points of the best observed solve rate as
  diagnostics only. The floor is predeclared and is not lowered after seeing results.

### The calibration rule (read twice)

This benchmark inverts normal instincts. **If the ceiling panel cannot clear the pre-registered
one-shot acceptance gate, the task is wrong for that ShallowSWE snapshot.** The v1 candidate gate is
75%. Small, medium, and large are assigned by floor-probe first-submit behavior:

| Size | Floor one-shot diagnostic | Repair-loop signal |
| --- | ---: | --- |
| Small | 70-100% | Solves cheaply, usually first submission |
| Medium | 30-70% | Solves, but spend or submissions separate models |
| Large | 0-40% | Cheap rows show high spend, more submissions, or cap-hit risk |

Author labels are hypotheses. Calibration data can move or reshape tasks. One-shot runs decide task
acceptance and size. Bounded repair-loop runs decide final CPSC. The full protocol lives in
`docs/calibration-protocol.md`.

## Task format

Use a Pier-compatible task structure similar to the public DeepSWE task layout. Each task is a folder:

```
tasks/<task-id>/
  task.toml          # [metadata], [calibration], verifier/agent/environment limits
  instruction.md     # exactly what the agent sees
  environment/
    Dockerfile       # reproducible isolated environment
  tests/
    verify.sh        # programmatic verifier, exits 0/1
  solution/          # reference solution, held out from the agent
  solution_alt/      # materially different valid solution, held out from the agent
  quality/
    requirements.json        # prompt/repo requirement to verifier-check map
    negative-controls.json   # intentionally bad solutions that must fail
```

- Verifiers are **programmatic only**. Test behavior, not implementation. No LLM judges anywhere in the scoring path.
- Every task runs in an isolated container with no internet access.
- `[calibration]` records task-admission provenance: snapshot id, ceiling/floor panels, current and
  target one-shot counts, pass counts, admission decision, and size-assignment decision. Candidate
  tasks may record pending high-N gates; accepted snapshot tasks must record accepted decisions.
- `quality/` records task-QA evidence declarations. Accepted snapshot tasks must map hidden checks
  to prompt or repo-contract requirements, record negative controls, and separately confirm those
  controls fail. The structural audit does not execute the declared controls.
- Evaluate Datacurve's Pier framework for the sandboxed execution layer before building anything custom. Fork and extend where possible; the goal is minimum time to first report.

### Task quality audit

Task QA is a separate gate from calibration. Before calibration, every candidate task must pass the
quality audit in `docs/task-quality-audit.md`:

1. Prompt-verifier consistency: every hidden verifier assertion maps to `instruction.md` or an
   existing public repo contract.
2. Implementation independence: reference and materially different alternate solutions pass.
3. Coverage sufficiency: no-op, hardcoded visible fixture, partial, malformed-row-skipping, and
   destructive-overreach controls fail.
4. Example consistency: prompt examples, visible fixtures, hidden expectations, and reference
   solution do not contradict each other.
5. Repair-loop fairness: hidden verifier feedback remains coarse and non-oracle.

OpenAI-style task-quality labels are `overly_strict_verifier`, `underspecified_prompt`,
`low_coverage_verifier`, and `misleading_prompt`. Calibration can expose these problems, but it does
not repair them. If a trajectory fails because the task is ambiguous or the verifier is too strict,
fix or reject the task before using that row as benchmark evidence.

### Contamination policy

Write every task from scratch. Adapt nothing from existing repos, commits, PRs, or public benchmark suites. Rationale: contamination here distorts *cost*, not correctness. A memorized solution takes fewer tokens than a derived one, and tokens are the entire product. Original trivial tasks are cheap to author; there is no excuse to copy.

Task generation workflow: source public GitHub and benchmark datasets only for abstract patterns,
author original project-shaped tasks, run prompt-verifier review, validate alternate solutions,
record task-quality evidence, then use the pinned-ceiling and measured-floor gates to place the
task. `docs/task-sourcing-methodology.md` is the task-authoring source of truth, and
`docs/task-quality-audit.md` is the task-QA source of truth.

Each public snapshot is frozen and fully reproducible. Once tasks, transcripts, and verifiers are
broadly published, future model-ranking claims require a new task-suite version or a held-out
private extension. Public v1 tasks are not reused indefinitely as live leaderboard ground truth.

## Harness

- **Agent scaffold**: mini-swe-agent, held constant across all models. ShallowSWE benchmarks models, not scaffolds. One scaffold, one prompt template, zero per-model tuning.
- **Repair loops**: use enough independent repair-loop seeds for the claim being made. Small-N
  one-shot probes are for plumbing and first-submit diagnostics. Calibration uses enough scored
  repair loops to estimate solve rate, loop spend, verifier-submission count, and cap-hit rate.
  Publish snapshots report uncertainty intervals.
- **Predeclared rollout counts**: v1 uses `N=1` for plumbing probes, `N=16` for task-admission
  one-shot ceiling gates, `N=10` for size-calibration floor probes, `N=10` repair-loop seeds for
  published scoring, and `N=20` for report-grade reruns of disputed frontier cells. Primary
  uncertainty intervals bootstrap over tasks within each category/size slice. Seed-level variation
  is reported as secondary stochasticity; seeds do not replace task diversity.
- **Model panels**: tiers are structural, not durable model names. Calibration ceiling and
  floor-probe panels freeze before task authoring and admission. The published leaderboard panel
  freezes before the full repair-loop run. Each snapshot publishes the exact `(model, effort,
  sampling_config)` panel used for that run. Model names belong in versioned panel files and
  snapshot appendices, not in the durable methodology.
- **Token accounting**: from API usage fields on every response, summed across the full repair loop.
  Pier/ATIF totals are acceptable only when they reconcile with recursive raw provider usage.
  Include cache read/write tokens and price them at the provider's cache rates.
- **Cache policy**: intra-run cache usage is scored and priced normally. Cross-run or global prompt
  cache effects are disabled where possible. If they cannot be disabled, run order is randomized
  and cache-hit rates are reported separately. Warm-cache and cold-cache pricing are never mixed in
  the same headline result.
- **Limits**: dollar cap, verifier-submission cap, wall-time cap, and agent-step cap. Dollar caps
  are safety limits, not intended difficulty controls, and must be set high enough that ceiling
  models rarely hit them during calibration. Verifier-submission caps prevent oracle probing. Step
  caps catch looped behavior. Wall-time caps are infra guards and are retried unless paired with a
  genuine step-cap failure.
- **Verifier feedback**: the harness may tell the agent only `Verification failed. Continue
  working.`, `Verification failed: runtime error.`, `Verification failed: missing required
  artifact.`, `Verification failed: output mismatch.`, or `Verification passed.` Hidden assertion
  messages, expected hidden outputs, fixture values, golden diffs, hidden line numbers, and
  answer-revealing stdout/stderr are never exposed. The harness reads only a sanitized
  machine-readable verifier class for repair-loop feedback and ignores raw hidden stdout/stderr for
  agent-facing context.
- **Verifier classes**: verifiers emit one of `passed`, `generic_failure`, `runtime_error`,
  `missing_required_artifact`, `output_mismatch`, or `verifier_infra_error`. `passed`,
  `generic_failure`, `runtime_error`, `missing_required_artifact`, and `output_mismatch` are scored
  verifier outcomes. `verifier_infra_error` is excluded and retried.
- **Output**: one flat repair-loop `results.json` per snapshot with canonical tokens, status, and
  provenance: `{schema_version, model, requested_model, resolved_model, provider, inference_gateway,
  upstream_provider, model_variant, reasoning_effort, temperature, sampling_config, task_id,
  category, size, loop, status, exclusion_reason, passed, stop_reason, verifier_submissions,
  input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens, turns,
  agent_steps, peak_context_tokens, gateway_reported_cost_usd, agent, agent_version, runner,
  runner_version, scaffold_prompt_hash, token_source, task_version, task_suite_version,
  verifier_hash, environment_image_digest, repo_commit_sha, price_sheet_version, price_sheet_date,
  seed, run_id, task_visibility, transcript_hash, started_at, finished_at}`. Raw rows store
  `gateway_reported_cost_usd` only as diagnostic reconciliation metadata; canonical dollars are
  derived from versioned price sheets in aggregate outputs.
- Every repair-loop transcript is stored and published. When the report says a model flailed across
  verifier submissions, the receipts are one click away. Published transcripts pass a redaction
  step for secrets, credentials, provider metadata, machine identifiers, and non-task
  infrastructure paths. Redaction must not remove model outputs, commands, code edits, verifier
  submissions, or agent-facing verifier feedback.

### Scored vs excluded rows

Normal verifier failures, dollar caps, verifier-submission caps, and agent-step caps are scored
failures when token usage is available. Context exhaustion after meaningful agent progress is
scored. Context exhaustion caused by task packaging, prompt construction, provider dispatch
mismatch, or scaffold overhead before meaningful work begins is excluded and fixed. Provider,
network, credential, credit, model-resolution, provider-dispatch, verifier-infrastructure failures,
and wall-time infra guards are excluded and retried until the target number of scored repair loops
is reached. Publish exclusion counts per model/task.

## Site

Single-page, DeepSWE-style in spirit: one thing to grasp in five seconds.

- **Hero: the single-model reliability-cost frontier.** Per category and size, show which single
  `model_config` is cheapest among rows that satisfy the snapshot's declared solve-rate floor.
  Solve-rate eligibility is computed over the category/size slice using the snapshot's declared
  task weights. Rows below the floor stay visible as diagnostics but are not recommended
  configurations. Eligible rows are ranked by point-estimate CPSC. If the cheapest eligible row's
  CPSC interval overlaps another eligible row's interval, or if another eligible row is within 10%
  of its point-estimate CPSC, the cell is disputed. All overlapping or near-frontier rows are rerun
  to `N=20`, and the `N=20` results replace `N=10` for that displayed comparison. If a recommended
  row clears the slice-level floor but has any task below 60% solve rate, the UI marks it
  "slice-aggregate only" rather than implying reliable performance on every task shape.
- **Workload index view.** Suite-level CPSC is a declared basket of routine work, with equal
  category/size/task weights for the v1 default and UI controls for user-adjusted workload weights.
  Do not average per-task CPSC directly. Use a weighted ratio:

```text
WeightedCPSC(m) =
  sum_t w_t * mean_spend(m,t)
  /
  sum_t w_t * solve_rate(m,t)
```

  where `mean_spend(m,t)` is average scored repair-loop spend for `model_config m` on task `t`,
  `solve_rate(m,t)` is successful scored repair loops divided by scored repair loops, and `w_t` is
  the declared workload weight for task `t`.
- **DeepSWE comparison.** When DeepSWE cost metadata is available, show hard-work CPSC vs ShallowSWE routine-work CPSC as the primary cross-benchmark scatter. Capability percentage vs routine CPSC is secondary context.
- Below the hero: leaderboard table (CPSC by category, sortable), methodology, per-task drill-down with browsable rollout transcripts, results.json and workload-index downloads.
- Snapshot-dated. A stale price sheet is worse than none; the date is prominent.

## Price Sheets

Public headline dollars use public list prices from a versioned price sheet. The UI may offer
user-adjusted prices, but they are separate from the headline snapshot. Before a public launch,
price sheets must expose a normalized schema with the fields below.

Minimum price-sheet fields:

```text
provider
model
resolved_model
currency = "USD"
effective_date = "YYYY-MM-DD"
input_per_mtok
output_per_mtok
reasoning_per_mtok
cache_read_per_mtok
cache_write_per_mtok
source_url
notes
```

Direct-provider and gateway prices are separate entries. A snapshot must record the price-sheet
version and date used to render canonical dollars.

## Build order

1. Fork DeepSWE / evaluate Pier. Get one task running end to end against two models with real token
   accounting. Prove the pipeline before writing the suite.
2. Freeze v1 protocol and calibration panels: single-model invariant, `model_config` identity,
   ceiling panel, floor-probe panel, solve-rate floor, rollout counts, cap defaults, aggregation
   formula, exclusion rules, price-sheet schema, and transcript redaction policy.
3. Author the 36-task suite with the measured-floor gate.
4. Freeze the published leaderboard panel.
5. Full panel run. Produce results.json.
6. Build the site around the reliability-cost frontier.
7. Launch artifact: one written report with the inversion findings, linking the live site.

## Open questions (decide before step 2)

- Final name check: confirm "ShallowSWE" has no collisions.
- Calibration ceiling/floor panels freeze before task authoring. The published leaderboard panel
  freezes before the full panel run.
- Reasoning-effort settings count as separate panel entries. The display and aggregate identity is `model_config`, which is `model` plus effort level when present.
- Cap values by task size and model tier, with calibration sanity checks for ceiling cap hits.

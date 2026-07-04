# ShallowSWE Methodology Notes

## Result Status

Final benchmark rows are bounded repair loops. Historical one-shot rollout rows are retained as
calibration diagnostics only.

Repair-loop rows are either `scored` or `excluded`.

Scored rows count toward solve rate, tokens per success, and CPSC. This includes normal verifier
failures, dollar caps, verifier-submission caps, agent-step caps, and context exhaustion after
meaningful agent progress when token usage is available.

Excluded rows do not count toward solve rate or CPSC. This includes provider, network, credential,
credit, model-resolution, provider-dispatch, verifier infrastructure failures, wall-time infra
guards, and context exhaustion caused by task packaging, prompt construction, provider dispatch
mismatch, or scaffold overhead before meaningful work begins. Exclusions should be retried until
each model-task pair has the target number of scored repair loops. Published summaries should
include exclusion counts.

## Token Convention

`input_tokens` uses the provider/gateway prompt-token convention. For OpenAI-style APIs, cached input tokens are included in prompt tokens. `cache_read_tokens` and `cache_write_tokens` are stored separately so cost derivation can price uncached input, cache reads, and cache writes without double-counting.

The cost formula is:

```text
uncached_input_tokens = input_tokens - cache_read_tokens - cache_write_tokens
derived_cost = uncached_input_tokens * input_rate
             + cache_read_tokens * cache_read_rate
             + cache_write_tokens * cache_write_rate
             + output_tokens * output_rate
```

`reasoning_tokens` are a subset of output tokens when the provider reports them.

Aggregate tables report total tokens, input tokens, output tokens, cache reads, cache writes,
reasoning tokens, turns, verifier submissions, cap hits, and dollar cost across the full repair
loop. Final CPSC is:

```text
CPSC = total model spend across scored repair-loop rows / number of successful repair loops
```

CPSC is computed per `model_config`; no scored row combines spend from multiple models.

Aggregation cells with zero successful repair loops have undefined CPSC and are displayed as "no
verified successes." Their spend, solve rate, and cap-hit rate remain part of the diagnostic table.

Raw rows may include `started_at` and `finished_at` for provenance, but wall-clock time is not a
reported metric. Wall-time stops are infra guards and should be retried unless the agent-step cap
corroborates genuine looping.

Token counts are durable rollout records, but they are not the cross-model currency. Tokenizers and
provider accounting can differ enough that the same text produces different billable token counts
across providers. Use raw tokens for per-model diagnostics such as flailing, repair-loop length,
and context appetite. Use price-sheet-derived measured dollars for cross-model and
reliability-cost comparisons.

Intra-run cache usage is scored and priced normally. Cross-run or global prompt-cache effects are
disabled where possible. If they cannot be disabled, run order is randomized and cache-hit rates are
reported separately. Warm-cache and cold-cache pricing are never mixed in the same headline result.

## Gateway Policy

OpenRouter is the default gateway for panel plumbing because it exposes the current DeepSWE model
set through one API. Official runs must still pin provider dispatch, disable fallbacks, record the
upstream provider per row, and run direct-provider audit checks per provider family.

Dollar metrics are gateway-aware. Tokens remain canonical, while gateway-reported cost is stored as reconciliation metadata. For OpenRouter runs, the price sheet should use OpenRouter model endpoint pricing, not direct-provider list pricing.

When gateway-reported costs are present, aggregate tables also report reconciliation fields comparing price-sheet-derived cost to gateway-reported cost. Non-zero deltas should be investigated by provider family before using the dollar ranking as a headline claim. Token rankings remain canonical when provider billing metadata is inconsistent.

Budget estimates are planning artifacts. They must include the token basis, task count, rollout count, priced row count, and missing price rows. A full-panel dollar estimate is only valid when every panel row resolves to a price entry. Broad seed panels should be guarded with an explicit max-budget preflight and should not be run end-to-end until the cheaper calibration ladder justifies that scope.

Use ShallowSWE's v1 target of 36 tasks for run budgeting. DeepSWE's 113-task count is only source metadata for the seed panel and should not drive ShallowSWE execution estimates.

## Workload Index

Task, category, and size metrics are the primary scientific objects. The suite-level CPSC is a
declared workload index: the price of a named basket of routine work, not a universal model score.

The default v1 basket uses equal category weights, equal size weights inside each category, and equal task weights inside each category-size cell. This prevents categories with more instantiated tasks from accidentally dominating the headline number. For incomplete suites, the index is normalized over observed tasks and reports `declared_coverage_weight` so preview numbers are not mistaken for full-suite numbers.

Reasoning effort is part of model identity. A model at `high`, `xhigh`, or any other reported effort level is a separate `model_config` point from the same base model at another effort level.

The site data contract is:

```text
task_weights = declared/default task weights for the visible basket
cells        = task-level metrics by model_config/category/size/task
models       = precomputed default basket summaries
```

A UI can implement sliders by changing category and size weights, recomputing normalized task
weights over the selected cells, and then calculating basket CPSC as a weighted ratio:

```text
WeightedCPSC(m) =
  sum_t weight_t * mean_spend(m,t)
  /
  sum_t weight_t * solve_rate(m,t)
```

Here, `mean_spend(m,t)` is average scored repair-loop spend for `model_config m` on task `t`,
`solve_rate(m,t)` is successful scored repair loops divided by scored repair loops, and `weight_t`
is the declared workload weight for task `t`. This is a weighted ratio, not an average of per-task
CPSC values, so failed-loop spend remains in the basket.

For one-shot calibration diagnostics, replace `mean_spend` with mean one-shot attempt cost and
`solve_rate` with first-submit pass rate. Tokens per success use the same denominator. This keeps
zero-success task cells in the basket instead of dropping their failed-loop spend.

## Single-Model Reliability-Cost Frontier

The primary ShallowSWE report is a single-model reliability-cost frontier, not a global leaderboard
and not a runtime dispatch policy. Each scored row runs exactly one `model_config`, defined as
`(model, effort, sampling_config)`, on a clean task sandbox. All agent turns, repair-loop
continuations, verifier-feedback responses, and cap outcomes within that row use the same
`model_config`. ShallowSWE does not use fallback, escalation, ensembling, judge models, retrying
with a different model, or transcript handoff inside a scored run. If that model fails or hits a
scored cap, no other model continues that run.

For final results, rank model configurations by measured bounded repair-loop CPSC, solve rate,
verifier submissions to success, and cap-hit rate. A row is eligible to be a recommended
configuration only if it clears the snapshot's declared solve-rate floor. For the hero frontier,
solve-rate eligibility is computed over the category/size slice using the snapshot's declared task
weights. The v1 default floor is 90% scored repair-loop solve rate. Rows below the floor remain
visible as raw measurements, but the site must not present them as recommended configurations.

If no row in a category/size slice reaches the floor, the site displays "no recommended
configuration" and shows the cheapest rows within two percentage points of the best observed solve
rate as diagnostics only. Eligible rows are ranked by point-estimate CPSC. If the cheapest eligible
row's CPSC interval overlaps another eligible row's interval, the UI labels them "statistically
tied" and displays both. The primary recommendation remains the lowest point estimate unless a
conservative view is selected.

A frontier cell is disputed if the cheapest eligible row's CPSC confidence interval overlaps
another eligible row's interval, or if another eligible row is within 10% of its point-estimate
CPSC. In disputed cells, all overlapping or near-frontier rows are rerun to `N=20`, and the `N=20`
results replace `N=10` for that displayed comparison. If a recommended row clears the slice-level
floor but has any task below 60% solve rate, the UI marks it "slice-aggregate only" rather than
implying reliable performance on every task shape.

This math assumes the benchmark's oracle verifier is free and perfect. Production verification has
cost and false negatives. ShallowSWE therefore measures an upper bound on savings from up-front
single-model selection.

## DeepSWE Comparison

The primary cross-benchmark comparison should use the same unit on both axes when available:

```text
x = DeepSWE hard-work CPSC
y = ShallowSWE routine-work basket CPSC
```

The mixed chart, DeepSWE pass rate vs ShallowSWE CPSC, is still useful as capability-vs-routine-cost context, but it should not replace the all-dollars chart when DeepSWE cost metadata is available.

## Calibration

The calibration protocol is defined in `docs/calibration-protocol.md`.

Each snapshot has two pre-registered calibration panels. The `ceiling_panel` contains frontier
`model_config`s used only to decide whether a candidate task is admissible for the snapshot. The
`floor_probe_panel` contains cheaper or lower-effort `model_config`s used to assign task size. The
calibration panels freeze before suite authoring and task admission. The broader published
leaderboard panel may freeze later, before the full repair-loop run.

The floor is empirical on ShallowSWE tasks. Do not use DeepSWE rank or a price sheet as the floor.
Run a floor-selection sweep across several cheap candidate pairs, then choose the primary
floor-probe configuration with useful dynamic range across the authored task set. Secondary
floor-probe configs are recorded for sensitivity analysis and trigger manual review if they
disagree with the primary assignment by more than one size band. A cheap pair that passes nearly
everything is a mid rung, not the floor.

The ceiling gate is evaluated against a pre-registered ceiling panel. The primary ceiling row is the
admission gate; optional audit rows are separate task-QA diagnostics, not fallbacks. A candidate
task is admitted only if at least one ceiling `model_config` clears the 75% one-shot acceptance gate
and verifier review finds no task flaw. The panel, seed count, pass counts, and admission decision
are recorded in task calibration evidence.

Calibration one-shot runs are quarantined from published leaderboard repair loops. Publish
snapshots use fresh repair-loop seeds and report Wilson intervals for solve rates plus bootstrap
intervals for CPSC.

Task manifests record calibration provenance: snapshot id, ceiling and floor-probe panels, current
and target one-shot counts, pass counts, admission decision, size-assignment decision, and notes.
Local candidate tasks may carry pending high-N decisions; calibrated snapshot tasks must record
accepted decisions.

## Price Sheets

Public headline dollars use public list prices from versioned price sheets. User-adjusted prices
may be shown in the UI, but they are separate from the headline snapshot. Direct-provider and
gateway prices are separate entries. Before public launch, price sheets must expose normalized
fields for provider, model, resolved model, currency, effective date, input/output/reasoning/cache
read/cache write rates per million tokens, source URL, and notes.

## Transcript Redaction

Published transcripts pass a redaction step for secrets, credentials, provider metadata, machine
identifiers, and non-task infrastructure paths. Redaction must not remove model outputs, commands,
code edits, verifier submissions, or agent-facing verifier feedback.

## Snapshot Policy

Each public snapshot is a frozen, reproducible historical artifact. Once task prompts, transcripts,
and verifiers are broadly published, future model-ranking claims require a new task-suite version or
a held-out private extension. Public v1 tasks can remain useful for regression and demonstration,
but not as indefinite live-leaderboard ground truth.

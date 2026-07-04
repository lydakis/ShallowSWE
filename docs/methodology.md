# ShallowSWE Methodology Notes

## Result Status

Rollout rows are either `scored` or `excluded`.

Scored rows count toward pass rate, tokens per success, and CPSC. This includes normal verifier failures, context-window failures, task caps, and agent timeouts when token usage is available.

Excluded rows do not count toward pass rate or CPSC. This includes provider, network, credential, credit, routing, and verifier infrastructure failures. Exclusions should be retried until each model-task pair has the target number of scored rollouts. Published summaries should include exclusion counts.

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

Aggregate tables report total tokens, input tokens, output tokens, cache reads, cache writes, reasoning tokens, turns, and dollar cost. Per-success metrics include failed scored attempts in the denominator through pass rate: for example, `tokens_per_success = mean_tokens_per_attempt / pass_rate`. Raw rows may include `started_at` and `finished_at` for provenance, but wall-clock time is not a reported metric.

## Gateway Policy

OpenRouter is the default gateway for panel plumbing because it exposes the current DeepSWE model set through one API. Official runs must still pin provider routing, disable fallbacks, record the upstream provider per row, and run direct-provider audit checks per provider family.

Dollar metrics are gateway-aware. Tokens remain canonical, while gateway-reported cost is stored as reconciliation metadata. For OpenRouter runs, the price sheet should use OpenRouter model endpoint pricing, not direct-provider list pricing.

When gateway-reported costs are present, aggregate tables also report reconciliation fields comparing price-sheet-derived cost to gateway-reported cost. Non-zero deltas should be investigated by provider family before using the dollar ranking as a headline claim. Token rankings remain canonical when provider billing metadata is inconsistent.

Budget estimates are planning artifacts. They must include the token basis, task count, rollout count, priced row count, and missing price rows. A full-panel dollar estimate is only valid when every panel row resolves to a price entry. Broad seed panels should be guarded with an explicit max-budget preflight and should not be run end-to-end until the cheaper calibration ladder justifies that scope.

Use ShallowSWE's v1 target of 36 tasks for run budgeting. DeepSWE's 113-task count is only source metadata for the seed panel and should not drive ShallowSWE execution estimates.

## Workload Index

Task, category, and tier metrics are the primary scientific objects. The suite-level CPSC is a declared workload index: the price of a named basket of routine work, not a universal model score.

The default v1 basket uses equal category weights, equal tier weights inside each category, and equal task weights inside each category-tier cell. This prevents categories with more instantiated tasks from accidentally dominating the headline number. For incomplete pilots, the index is normalized over observed tasks and reports `declared_coverage_weight` so preview numbers are not mistaken for full-suite numbers.

Reasoning effort is part of model identity. A model at `high`, `xhigh`, or any other reported effort level is a separate `model_config` point from the same base model at another effort level.

The site data contract is:

```text
task_weights = declared/default task weights for the visible basket
cells        = task-level metrics by model_config/category/tier/task
models       = precomputed default basket summaries
```

A UI can implement sliders by changing category and tier weights, recomputing normalized task weights
over the selected cells, and then calculating CPSC as weighted mean cost per attempt divided by
weighted pass rate. Tokens per success use the same denominator. This keeps zero-success task cells
in the basket instead of dropping their retry tax.

T4 rows are normal workload rows. They enter `task_weights`, `cells`, and `models` the same way
T1-T3 rows do.

## DeepSWE Comparison

The primary cross-benchmark comparison should use the same unit on both axes when available:

```text
x = DeepSWE hard-work CPSC = mean_cost_usd / pass_rate
y = ShallowSWE routine-work basket CPSC
```

The mixed chart, DeepSWE pass rate vs ShallowSWE CPSC, is still useful as capability-vs-routine-cost context, but it should not replace the all-dollars chart when DeepSWE cost metadata is available.

## Panel Floor

The calibration floor is empirical on shallow tasks. Do not use DeepSWE rank on hard tasks as the ShallowSWE floor. Gate candidate tasks against the cheapest/smallest panel candidates first, then use the observed weakest row on shallow tasks as the floor for the saturation gate.

Pilot calibration is two-stage. First, run a cheap N=1 plumbing and sizing sweep across a narrowed broad model subset. Then run N=5 or more on the 2-3 cheapest/weakest floor candidates before accepting tasks against the >=80% pass saturation gate.

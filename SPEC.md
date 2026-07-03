# ShallowSWE — Specification v0.1

A benchmark for the easy parts. Every task is designed so that every model in the panel can solve it. The score is not accuracy. The score is cost.

ShallowSWE is an independent benchmark inspired by DeepSWE's rigor. It is not affiliated with DeepSWE, Datacurve, Harbor, or Pier.

## Thesis

Most real-world LLM usage is routine: small bugfixes, formatting, extraction, git operations, short agentic chains. Existing benchmarks measure capability at the frontier and say nothing about which model is *economical* for everyday work. ShallowSWE holds difficulty near zero and measures efficiency: cost per successful completion, per task category, per model. The headline output is a crossover map showing where small models stop being cheap and large models stop being wasteful.

Name is a deliberate foil to DeepSWE. Same rigor, opposite end of the pool.

## Core metric

**Cost per successful completion (CPSC)**, per task, per model:

```
CPSC = mean_cost_per_attempt / pass_rate
```

- `mean_cost_per_attempt`: average dollar cost across all rollouts (pass and fail), derived from canonical token fields and a dated price sheet. Published provider prices are data, not baked into rollout rows.
- `pass_rate`: fraction of rollouts that pass the verifier.
- A model that passes 90% of the time pays an implicit 1.11x retry tax. This keeps a cheap-but-flaky model from gaming the leaderboard.

Report alongside CPSC:
- **Tokens per successful completion** (same formula, tokens instead of dollars). This is the pricing-independent, durable number. Dollars change; tokens are the scientific object.
- **Turns to completion** (agentic tasks): number of agent-environment round trips.
- Pass rate itself, for transparency.

Exclude wall-clock time entirely. It depends on provider load and host hardware and is not reproducible (DeepSWE v1.1 dropped it for the same reason).

## Task suite

The durable suite design lives at the shape level. See `docs/task-shape-catalog.md` for the current catalog used to instantiate original tasks.

### Categories (the routing axis)

Four categories. Each answers "which model should I route this *kind* of work to?"

1. **Fix** — deterministic coding: small bugfixes, write a function to spec, add a missing test. One obvious correct behavior.
2. **Transform** — extraction and reshaping: messy JSON to CSV, log summarization to a fixed schema, config format migration. Pure "do the thing, do not editorialize" work where verbose models burn tokens.
3. **Operate** — multi-step agentic work in a repo: rename a symbol across files, follow a config chain to change a value, resolve a trivial merge conflict, git operations (branch, cherry-pick, amend). This is where small models flail and inversions live.
4. **Invoke** — tool-call precision: given a small set of tools (file ops, a fake ticket API, a fake search), accomplish a goal. Measures whether the model takes 3 calls or 30. Includes ticket-cutting-style tasks: turn a bug report into a well-formed structured ticket via the tool.

### Tiers (the difficulty axis within a category)

Three tiers per category. Tiers turn each crossover from a point into a curve: "Model X is cheaper until tier 2, then the flailing tax flips it."

- **T1** — trivial. Single obvious step. Any model passes near 100%.
- **T2** — routine. Two or three steps, still one clear path.
- **T3** — mildly gnarly. Requires a bit of orientation (reading two files, one small decision) but still solidly within every panel model's ability.

### Sizing

- v1 target: 4 categories × 3 tiers × 3 tasks = **36 tasks**.
- Panel: ~8 models, 4 rollouts each → ~1,150 runs per snapshot. Keep this in budget; it reruns on every model launch.

### The saturation rule (read twice)

This benchmark inverts normal instincts. **If a task turns out to be hard, cut it or simplify it.** Acceptance criterion for every task: the weakest model in the panel passes at **≥80%** across rollouts. A task that separates models on accuracy has failed calibration and leaves the suite. Difficulty is a bug here, not a feature. During suite construction, run every candidate task against the weakest panel model first and use its pass rate as the gate.

## Task format

Use a Pier-compatible task structure similar to the public DeepSWE task layout. Each task is a folder:

```
tasks/<category>/<tier>/<task-id>/
  task.toml          # metadata: category, tier, language, image, limits, panel-gate results
  instruction.md     # exactly what the agent sees
  environment/
    Dockerfile       # reproducible isolated environment
  tests/
    verify.sh        # programmatic verifier, exits 0/1
  solution/          # reference solution, held out from the agent
```

- Verifiers are **programmatic only**. Test behavior, not implementation. No LLM judges anywhere in the scoring path.
- Every task runs in an isolated container with no internet access.
- Evaluate Datacurve's Pier framework for the sandboxed execution layer before building anything custom. Fork and extend where possible; the goal is minimum time to first report.

### Contamination policy

Write every task from scratch. Adapt nothing from existing repos, commits, PRs, or public benchmark suites. Rationale: contamination here distorts *cost*, not correctness. A memorized solution takes fewer tokens than a derived one, and tokens are the entire product. Original trivial tasks are cheap to author; there is no excuse to copy.

Task generation workflow: source public GitHub and benchmark datasets only for abstract patterns, author original project-shaped tasks, run prompt-verifier review, validate alternate solutions, then use the weakest-model gate to confirm saturation. `docs/task-sourcing-methodology.md` is the task-quality source of truth.

## Harness

- **Agent scaffold**: mini-swe-agent, held constant across all models. ShallowSWE benchmarks models, not scaffolds. One scaffold, one prompt template, zero per-model tuning.
- **Rollouts**: 4 per task per model. Report mean and range.
- **Model panel v1** (adjust to what is current at build time):
  - Small: Claude Haiku 4.5, GPT-5 mini-class, one small open model (Qwen-class)
  - Mid: Claude Sonnet 4.6, GPT-5.5 standard
  - Large: Claude Opus 4.8, Claude Fable 5, GPT-5.5 high-effort
- **Token accounting**: from API usage fields on every response, summed per rollout. Pier/ATIF totals are acceptable only when they reconcile with recursive raw provider usage. Include cache read/write tokens and price them at the provider's cache rates.
- **Limits**: per-task turn cap and token cap in task.toml. A rollout that hits a cap counts as a failure at full incurred cost. Caps should be generous (5-10x the reference solution's usage) so they catch flailing, not normal variance.
- **Output**: one flat `results.json` per snapshot with canonical tokens, status, and provenance: `{schema_version, model, requested_model, resolved_model, provider, inference_gateway, upstream_provider, model_variant, reasoning_effort, temperature, sampling_config, task_id, category, tier, rollout, status, exclusion_reason, passed, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens, turns, peak_context_tokens, gateway_reported_cost_usd, agent, agent_version, runner, runner_version, scaffold_prompt_hash, token_source, started_at, finished_at}`. Dollar fields are derived later from versioned price sheets.
- Every rollout's full transcript is stored and published. When the report says a model flailed for 40 turns, the receipts are one click away.

### Scored vs excluded rows

Normal verifier failures, context-window failures, task caps, and agent timeouts are scored failures when token usage is available. Provider, network, credential, credit, routing, and verifier infrastructure failures are excluded and retried until the target number of scored rollouts is reached. Publish exclusion counts per model/task.

## Site

Single-page, DeepSWE-style in spirit: one thing to grasp in five seconds.

- **Hero: the crossover map.** Per category, CPSC vs tier as a line per model. Inversion points (where a bigger model becomes cheaper than a smaller one) visually highlighted. This chart is the product; everything else supports it.
- **Workload index view.** Suite-level CPSC is a declared basket of routine work, with equal category/tier/task weights for the v1 default and UI controls for user-adjusted workload weights.
- **DeepSWE comparison.** When DeepSWE cost metadata is available, show hard-work CPSC vs ShallowSWE routine-work CPSC as the primary cross-benchmark scatter. Capability percentage vs routine CPSC is secondary context.
- Below the hero: leaderboard table (CPSC by category, sortable), methodology, per-task drill-down with browsable rollout transcripts, results.json and workload-index downloads.
- Snapshot-dated. A stale price sheet is worse than none; the date is prominent.

## Build order

1. Fork DeepSWE / evaluate Pier. Get one task running end to end against two models with real token accounting. Prove the pipeline before writing the suite.
2. Author the 36-task suite with the weakest-model gate.
3. Full panel run. Produce results.json.
4. Build the site around the crossover chart.
5. Launch artifact: one written report with the inversion findings, linking the live site.

## Open questions (decide before step 2)

- Final name check: confirm "ShallowSWE" has no collisions.
- Exact model panel at build time (models move fast; freeze the panel at step 3, not before).
- Reasoning-effort settings count as separate panel entries. The display and aggregate identity is `model_config`, which is `model` plus effort level when present.

# ShallowSWE

An independent benchmark for the easy parts of software work.

ShallowSWE is inspired by DeepSWE's rigor, but is not affiliated with DeepSWE, Datacurve, or Pier. The benchmark target is different: ShallowSWE holds task difficulty near saturation and measures cost per successful completion by task category, tier, and model.

## Current Shape

- `SPEC.md` is the v0.1 product spec and source of truth.
- `tasks/` is a Pier-compatible local dataset. `py-normalize-username` is harness smoke; the four quality-gate candidates are the first realistic suite slice.
- `src/shallowswe/` contains ShallowSWE metadata validation, Pier result export, and aggregation.
- `prices/` contains dated provider price sheets used to derive dollar metrics from token usage.
- `panels/` contains seed and preview model-panel manifests. DeepSWE-aligned manifests are starting points, not the final ShallowSWE panel.
- `docs/task-shape-catalog.md` defines durable task shapes used to instantiate original tasks.
- `docs/task-sourcing-methodology.md` defines how official benchmark tasks are mined, authored, reviewed, and calibrated.
- `docs/pilot-plan.md` records the calibration plan. The July 3 pilot snapshot uses the first four realistic tasks.
- Pier owns execution, sandboxing, agents, verifier runs, and trajectories.

## Quick Checks

```sh
uv run python -m unittest discover -s tests
uv run shallowswe tasks tasks
uv run pier run -p tasks/py-normalize-username --agent oracle --env docker --job-name shallowswe_oracle_probe --jobs-dir /tmp/shallowswe-pier -n 1 -k 1 -q
uv run shallowswe export-pier /tmp/shallowswe-pier/shallowswe_oracle_probe --tasks-root tasks > /tmp/shallowswe-results.json
uv run shallowswe aggregate /tmp/shallowswe-results.json
```

Add `--prices prices/openai-2026-07-03.json` when the result rows use models covered by that price sheet. Aggregates group by `model_config` by default, so reasoning-effort variants are separate rows.

Build the site-ready workload index and optional DeepSWE all-dollars comparison:

```sh
uv run shallowswe workload-index /tmp/shallowswe-results.json \
  --prices prices/openrouter-2026-07-03.json \
  > /tmp/shallowswe-workload-index.json

uv run shallowswe compare-deepswe /tmp/shallowswe-workload-index.json \
  > /tmp/shallowswe-deepswe-comparison.json
```

The workload index contains `task_weights`, per-model/task `cells`, and precomputed default `models`. A UI can recompute custom baskets client-side by changing category/tier weights and applying them to the cell metrics.

Estimate a panel before running it. The July 3 expanded publish pilot includes GLM 5.2 at high effort, Fable at low effort, low and medium rows for GPT-5.5, Claude Opus 4.8, and Claude Sonnet 5, plus Gemini medium and Kimi default. It excludes non-DeepSWE models:

```sh
uv run shallowswe estimate-panel panels/deepswe-v1.1-expanded-pilot.json \
  --prices prices/openrouter-2026-07-03.json \
  --task-count 4 --rollouts 3 \
  --input-tokens 83820 --output-tokens 4119 --cache-read-tokens 58756 \
  --max-budget-usd 100 --fail-over-budget
```

OpenRouter smoke runs should cap model output while plumbing is being tested:

```sh
uv run pier run -p tasks --include-task-name py-normalize-username \
  --agent mini-swe-agent \
  --model openrouter/google/gemini-3.5-flash \
  --agent-kwarg 'model_kwargs={"max_tokens":512}' \
  --env docker \
  --env-file /Users/lydakis/Developer/blue/apps/supervisor/.env.local \
  --agent-env 'OPENROUTER_API_KEY=${OPENROUTER_API_KEY}' \
  --job-name shallowswe_openrouter_gemini35_cap_probe \
  --jobs-dir /tmp/shallowswe-pier -n 1 -k 1 -q --yes
```

## Boundary

Do not build a ShallowSWE harness unless Pier cannot satisfy a concrete requirement. Local code should stay focused on the ShallowSWE problem definition: shallow-task metadata, calibration state, token normalization, price-sheet based CPSC aggregation, and site-ready exports.

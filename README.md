# ShallowSWE

An independent benchmark for the easy parts of software work.

ShallowSWE is inspired by DeepSWE's rigor, but is not affiliated with DeepSWE, Datacurve, or Pier.
The benchmark target is different: ShallowSWE pins a frontier ceiling, dials task size by a
floor-probe panel, and measures bounded repair-loop cost per successful completion by task
category, size, and model configuration.

## Current Shape

- `SPEC.md` is the v0.1 product spec and source of truth.
- `tasks/` is a Pier-compatible local dataset. It currently spans `code`, `artifact`, and `workflow` tasks across `small`, `medium`, and `large` sizes. `py-normalize-username` is harness smoke; the remaining tasks are realistic candidate or calibrated benchmark packets.
- `src/shallowswe/` contains metadata validation, the shared repair-loop protocol, Kaggle and Pier
  adapters, result export, and aggregation.
- `prices/` contains dated provider price sheets used to derive dollar metrics from token usage.
- `panels/` contains seed, preview, and calibration model-panel manifests. `shallowswe-calibration-v0.1` is the cheap anchor panel for size calibration; DeepSWE-aligned publish manifests are starting points, not the final ShallowSWE panel.
- `docs/task-shape-catalog.md` defines durable task shapes used to instantiate original tasks.
- `docs/calibration-protocol.md` defines pinned-ceiling, measured-floor calibration and the bounded
  repair-loop protocol.
- `docs/task-selection-rubric.md` defines which work packets belong in ShallowSWE.
- `docs/verifier-contract.md` defines what a passing rollout must prove and how task verifiers are reviewed.
- `docs/task-sourcing-methodology.md` defines how official benchmark tasks are mined, authored, reviewed, and calibrated.
- `docs/calibration-log.md` records size-calibration runs and admission decisions.
- `docs/pilot-plan.md` records the path from the 36-task scaffold to a calibrated v1 snapshot.
- Kaggle is the primary published repair-loop backend. Pier/Harbor remains the parallel local and
  calibration backend. `tasks/` is the single source of truth for both.
- `docs/kaggle-runner.md` documents packaging, isolation, parity, live conformance, and operations.

## Quick Checks

ShallowSWE has two run modes:

- **One-shot calibration mode**: current Pier-style runs. Use for task admission, the 75% ceiling
  gate, floor selection, and size calibration.
- **Bounded repair-loop scoring mode**: final published CPSC. Use only after the accepted task set
  is fixed. Each scoring row runs one `(model, effort)` pair only; ShallowSWE v1 does not fall back
  to another model inside a run.

```sh
uv run python -m unittest discover -s tests
uv run shallowswe tasks tasks
uv run pier run -p tasks/py-normalize-username --agent oracle --env docker --job-name shallowswe_oracle_probe --jobs-dir /tmp/shallowswe-pier -n 1 -k 1 -q
uv run shallowswe export-pier /tmp/shallowswe-pier/shallowswe_oracle_probe --tasks-root tasks > /tmp/shallowswe-results.json
uv run shallowswe aggregate /tmp/shallowswe-results.json
```

Build a private Kaggle deployment bundle from the same canonical task packet:

```sh
uv run shallowswe kaggle-pack tmp/kaggle-smoke-bundle \
  --task-id py-normalize-username \
  --tasks-root tasks \
  --config-file configs/mini-swe-agent-repair-loop-preview.yaml \
  --mini-swe-agent-source-dir /Users/lydakis/Developer/oss/mini-swe-agent
```

Add `--prices prices/openai-2026-07-03.json` when the result rows use models covered by that price sheet. The `aggregate` command summarizes one-shot rollout rows for calibration diagnostics. Final benchmark snapshots use bounded repair-loop rows and `aggregate-repair-loops`. Aggregates group by `model_config` by default, so reasoning-effort variants are separate rows.

Build the site-ready workload index and optional DeepSWE all-dollars comparison:

```sh
uv run shallowswe workload-index /tmp/shallowswe-results.json \
  --prices prices/openrouter-2026-07-03.json \
  > /tmp/shallowswe-workload-index.json

uv run shallowswe compare-deepswe /tmp/shallowswe-workload-index.json \
  > /tmp/shallowswe-deepswe-comparison.json
```

The workload index contains `task_weights`, per-model/task `cells`, and precomputed default
`models`. A UI can recompute custom baskets client-side by changing category/size weights and
applying them to the cell metrics.

Estimate a panel before running it. The July 3 expanded publish pilot includes GLM 5.2 at high
effort, Fable at low effort, low and medium rows for GPT-5.5, Claude Opus 4.8, and Claude Sonnet 5,
plus Gemini medium and Kimi default. It excludes non-DeepSWE models:

```sh
uv run shallowswe estimate-panel panels/deepswe-v1.1-expanded-pilot.json \
  --prices prices/openrouter-2026-07-03.json \
  --task-count 4 --rollouts 3 \
  --input-tokens 83820 --output-tokens 4119 --cache-read-tokens 58756 \
  --max-budget-usd 100 --fail-over-budget
```

Audit the pre-registered v1 calibration plan before starting the high-N calibration runs:

```sh
uv run shallowswe calibration-plan configs/shallowswe-v1-calibration-plan.json
```

The plan currently has two one-shot calibration groups: primary ceiling admission at `N=16` and
floor size calibration at `N=10`. A valid plan can still require explicit budget approval; the
ceiling phase is intentionally marked that way under the conservative July 4 estimate.

Use the calibration panel for the floor-selection sweep. Calibration one-shot rollouts are not
published leaderboard repair loops. A 36-task, 10-rollout sweep on the current cheap candidate
panel is a sizing diagnostic. The final floor is the pair with useful repair-loop solve-rate and
cap-hit spread, not the cheapest row:

```sh
uv run shallowswe estimate-panel panels/shallowswe-calibration-v0.1.json \
  --prices prices/openrouter-2026-07-03.json \
  --task-count 36 --rollouts 10 \
  --input-tokens 150000 --output-tokens 8000 --cache-read-tokens 100000 \
  --max-budget-usd 500 --fail-over-budget
```

After exporting Pier results, summarize floor candidates:

```sh
uv run shallowswe select-floor /tmp/shallowswe-floor-selection.json \
  --saturation-threshold 0.85
```

Evaluate the one-shot ceiling gate:

```sh
uv run shallowswe ceiling-gate /tmp/shallowswe-ceiling-results.json \
  --pass-threshold 0.75 --target-rollouts 16
```

OpenRouter smoke runs should cap model output while plumbing is being tested:

```sh
uv run pier run -p tasks --include-task-name py-normalize-username \
  --agent mini-swe-agent \
  --model openrouter/google/gemini-3.5-flash \
  --agent-kwarg max_tokens=512 \
  --agent-kwarg config_file=configs/mini-swe-agent-calibration.yaml \
  --env docker \
  --env-file /Users/lydakis/Developer/blue/apps/supervisor/.env.local \
  --agent-env 'OPENROUTER_API_KEY=${OPENROUTER_API_KEY}' \
  --job-name shallowswe_openrouter_gemini35_cap_probe \
  --jobs-dir /tmp/shallowswe-pier -n 1 -k 1 -q --yes
```

## Boundary

Keep runner-specific code thin. The shared controller owns repair-loop semantics, while Kaggle and
Pier own only their transport, sandbox, and verifier adapters. Do not fork task definitions or
methodology between backends.

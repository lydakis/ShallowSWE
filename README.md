# ShallowSWE

An independent benchmark for the easy parts of software work.

ShallowSWE is inspired by DeepSWE's rigor, but is not affiliated with DeepSWE, Datacurve, or Pier.
The benchmark target is different: ShallowSWE measures reference-budget cost per verified
completion under one bounded repair loop, separating work category, empirical floor pressure,
reference budget, and structural scope.

## Current Shape

- `docs/white-paper-v0.4.2.md` is the normative methodology source of truth.
- `docs/six-task-pilot-protocol-v0.3.md` is the normative protocol-validation pilot guide.
- `docs/protocol-governance.md` defines document precedence, freeze rules, runner roles, and
  evidence classes.
- `SPEC.md` is retained as the legacy v0.1 implementation specification while the v0.4.2 schema
  migration is completed.
- `tasks/` is a Pier-compatible local dataset. It currently spans `code`, `artifact`, and `workflow` tasks across `small`, `medium`, and `large` sizes. `py-normalize-username` is harness smoke; the remaining tasks are realistic candidate or calibrated benchmark packets.
- `src/shallowswe/` contains metadata validation, the shared repair-loop protocol, Kaggle and Pier
  adapters, result export, and aggregation.
- `prices/` contains dated provider price sheets used to derive dollar metrics from token usage.
- `panels/` contains seed, preview, and calibration model-panel manifests. `shallowswe-calibration-v0.1` is the cheap anchor panel for size calibration; DeepSWE-aligned publish manifests are starting points, not the final ShallowSWE panel.
- `docs/task-shape-catalog.md` defines durable task shapes used to instantiate original tasks.
- `docs/calibration-protocol.md` records the pre-v0.4.2 size-calibration implementation history.
- `docs/task-selection-rubric.md` defines which work packets belong in ShallowSWE.
- `docs/verifier-contract.md` defines what a passing rollout must prove and how task verifiers are reviewed.
- `docs/task-quality-audit.md` defines the publishable prompt/verifier QA evidence required before
  calibration and scoring.
- `docs/task-sourcing-methodology.md` defines how official benchmark tasks are mined, authored, reviewed, and calibrated.
- `docs/calibration-log.md` records size-calibration runs and admission decisions.
- `docs/pilot-plan.md` records the pre-v0.4.2 build plan and is not a launch manifest.
- Kaggle is the primary official pilot backend. Pier/Harbor remains the parallel portability and
  local-reproduction backend. Codex subscription runs are development-only. `tasks/` is the single
  authored source for every runner.
- Docker is the clean-sandbox backend for local deterministic task QA. It does not replace Kaggle
  as the official funded runner.
- `docs/kaggle-runner.md` documents packaging, isolation, parity, live conformance, and operations.

## Quick Checks

ShallowSWE has three evidence modes:

- **Deterministic QA**: reference, alternate, negative-control, verifier, isolation, and schema
  checks. These are not model evidence.
- **One-shot calibration**: anchor admission and floor-pressure measurement under frozen identities.
- **Bounded repair-loop calibration/scoring**: permissive policy calibration, fresh anchor
  confirmation, and later leaderboard scoring. Each row runs one immutable model and agent policy;
  there is no fallback inside a row.

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

Add `--prices prices/openai-2026-07-03.json` when the result rows use models covered by that price sheet. The `aggregate` command summarizes one-shot rollout rows for calibration diagnostics. Final benchmark snapshots use bounded repair-loop rows and `aggregate-repair-loops`. Migrated repair-loop rows group by immutable model-config and agent-policy IDs by default; legacy rows retain the old model/category/size grouping.

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

Build and execute task-quality evidence before calibration. The first command audits declarations,
hash-bound executions, and independent routine-review records. The second runs three reference
replicates, one alternate solution, and every declared negative control in fresh network-disabled
Docker containers:

```sh
uv run shallowswe task-quality tasks
uv run shallowswe execute-task-quality tasks \
  --task-id env-flags-to-json \
  --task-id access-log-to-incidents
```

For the six-task pilot, `pilot-review-pack` exports blind reviewer materials without solutions,
hidden verifiers, or trajectories. `pilot-review-import` validates the complete set before importing
the six hash-bound independent-review forms.

Expand the protocol-validation schedule and run the fail-closed preflight before any official
canary launch:

```sh
uv run shallowswe pilot-schedule \
  configs/shallowswe-six-task-pilot-v0.3.json \
  configs/shallowswe-six-task-pilot-v0.3-schedule.json
uv run shallowswe pilot-launch-plan \
  configs/shallowswe-six-task-pilot-v0.3.json \
  configs/shallowswe-six-task-pilot-v0.3-schedule.json \
  configs/shallowswe-six-task-pilot-v0.3-launch-plan.json
uv run shallowswe pilot-readiness configs/shallowswe-six-task-pilot-v0.3.json
```

After independent routine review, build the final Kaggle bundle with `--pilot-manifest`,
`--pilot-schedule`, `--pilot-launch-plan`, and `--price-sheet`. Freeze hashes only after the bundle
is final:

```sh
uv run shallowswe pilot-freeze configs/shallowswe-six-task-pilot-v0.3.json \
  --runner-bundle /tmp/shallowswe-six-task-v0.3-freeze-candidate \
  --price-sheet prices/openai-2026-07-06.json \
  --write
```

The freeze command refuses to write while any quality, routine-review, schedule, launch-plan,
bundle, or identity gate is incomplete. See `docs/six-task-pilot-launch-runbook.md`.

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

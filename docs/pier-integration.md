# Pier Integration Notes

Date checked: 2026-07-03.

ShallowSWE is independent from DeepSWE. Pier is useful because it is a standard open-source eval runner with sandboxing, agents, verifier execution, token fields, and a trajectory viewer.

## What We Use From Pier

- Local task dataset execution via `pier run -p tasks`.
- Standard agents, especially `mini-swe-agent`.
- Docker or Modal environments.
- Programmatic verifier execution.
- Trial-level `result.json` files.
- Agent trajectories and token totals.

## What ShallowSWE Owns

- The problem definition in `SPEC.md`.
- Original shallow tasks.
- Category and size taxonomy: Code, Artifact, Workflow; small, medium, large.
- Calibration rules, including pinned-ceiling and measured-floor gates.
- Normalized `results.json` for the ShallowSWE site.
- Versioned price sheets.
- Bounded repair-loop CPSC and token-per-success reporting.

## Task Layout

Use Pier's local task format directly:

```text
tasks/<task-id>/
  task.toml
  instruction.md
  environment/
  solution/
  tests/
```

Put ShallowSWE-specific fields in `[metadata]` and `[calibration]`, not in custom directory
structure:

```toml
[metadata]
category = "code"
size = "small"
shape = "implement-to-spec"
subtype = "single-function-bugfix"

[calibration]
calibration_snapshot_id = "shallowswe-v0.1-candidate-2026-07-04"
admission_decision = "candidate_pending_high_n"
size_assignment_decision = "candidate_pending_high_n_floor"
```

## Current Decision

Kaggle is the primary backend for official pilot evidence because funded Kaggle capacity is
available. Pier/Harbor remains supported as the parallel local-reproduction and portability
backend. Pier results remain eligible for pooled model evidence unless immutable policy or observed
behavior materially differs. Rows are presumptively equivalent across Pier and Kaggle when the
canonical model, task, agent policy, controls, and continuation behavior match. Both paths consume
`tasks/` and call the shared repair-loop protocol, and every row retains runner, gateway, route, and resolved-model
provenance. See `docs/protocol-governance.md` and `docs/kaggle-runner.md`.

## Repair-Loop Continuation

The current Pier `mini-swe-agent` integration is enough for one-shot calibration and filesystem
plumbing, but it is not enough for final repair-loop scoring. The wrapper launches a fresh
`mini-swe-agent` CLI process for each agent run, then Pier reads the resulting trajectory as output
metadata. It does not feed the prior assistant/tool messages back into the next submission.

Reusing the same sandbox would preserve edited files, but it would still be a fresh model
conversation with appended feedback. That is a useful smoke test, not a scored ShallowSWE repair
loop.

For the v1 repair-loop pilot, ShallowSWE uses an import-path Pier agent:
`shallowswe.pier_agents.resumable_mini_swe_agent:ResumableMiniSweAgent`. It uploads the local
`lydakis/mini-swe-agent` fork into the task container, installs it into a venv, runs the first
submission with `--task`, and runs later submissions with `--resume-from` plus sanitized
`--resume-feedback`. That keeps the same workspace and conditions the next model call on the prior
trajectory/messages.

Before the first official canary, use the v0.4.2 stage-aware preflight introduced by the schema
migration. The legacy capability-only command remains useful for historical smoke plans:

```sh
uv run shallowswe repair-loop-pilot-plan configs/shallowswe-repair-loop-pilot-v0.1.json
```

The legacy plan reporting `ready_for_final_protocol_pilot = true` does not authorize official spend.
The v0.4.2 preflight must additionally freeze immutable identities, evidence class, task quality,
stage allocation, censoring limits, price sheet, and cumulative budget.

## Accounting Decision

Treat tokens as canonical and dollars as derived. The exporter prefers Pier's ATIF `final_metrics`
only when they reconcile with recursive raw provider usage in the mini-swe-agent trajectory. Pier or
gateway `cost_usd` is stored only as `gateway_reported_cost_usd` reconciliation metadata;
price-sheet derived repair-loop CPSC remains the headline dollar metric.

OpenRouter may be used for panel plumbing or the optional preregistered comparator. The canonical
six-task pilot uses Kaggle. Every official or optional row must pin upstream provider dispatch,
disable gateway fallbacks, and record both
`inference_gateway` and `upstream_provider` in each row. Provider, network, credit, credential,
model-resolution, provider-dispatch, verifier-infra, and wall-time guard failures are excluded from
CPSC and retried; model failures inside the repair loop are scored.

## Cheap Codex Exec Calibration

Pier ships a native `codex` agent, so ShallowSWE does not need a custom Codex harness for cheap
development probes. Use it for prompt, verifier, floor-shape, or plumbing triage only. These rows
remain development evidence even if continuation works; the canonical pilot runs through Kaggle.

Budget the Codex mini panel before running it:

```sh
uv run shallowswe estimate-panel panels/shallowswe-codex-mini-calibration-v0.1.json \
  --prices prices/openai-2026-07-06.json \
  --task-count 18 \
  --rollouts 3 \
  --input-tokens 10000 \
  --output-tokens 1000 \
  --max-budget-usd 5 \
  --fail-over-budget
```

For ChatGPT subscription-backed runs, use the local wrapper agent so Pier's filtered egress allows
the `chatgpt.com` Codex endpoints while the task itself still has no general internet. The wrapper
uses Codex `auth.json`; do not pass `OPENAI_API_KEY` for this mode.

Run a single subscription-backed Codex row through Pier:

```sh
CODEX_FORCE_AUTH_JSON=true uv run pier run \
  --path tasks \
  --include-task-name 'env-flags-to-json' \
  --job-name shallowswe_codex_subscription_gpt54_mini_low_smoke \
  --jobs-dir /tmp/shallowswe-pier \
  --n-attempts 1 \
  --n-concurrent 1 \
  --agent-import-path shallowswe.pier_agents.codex_subscription_agent:CodexSubscriptionAgent \
  --model openai/gpt-5.4-mini \
  --agent-kwarg version=0.142.0 \
  --agent-kwarg reasoning_effort=low \
  --agent-env CODEX_FORCE_AUTH_JSON=true \
  --env docker \
  --yes
```

For an ultra-cheap probe, use `--agent-kwarg reasoning_effort=none`; for a more coding-capable cheap
probe, use `low`. The Pier Codex agent records Codex JSONL sessions and converts them to ATIF, so
the normal ShallowSWE export path applies:

```sh
uv run shallowswe export-pier \
  /tmp/shallowswe-pier/shallowswe_codex_subscription_gpt54_mini_low_smoke \
  --tasks-root tasks > /tmp/shallowswe-codex-mini-rollouts.json
```

To size the current local task set with the subscription path, run:

```sh
uv run python scripts/run_codex_subscription_sizing.py --floor-attempts 3 --concurrency 1
```

That runner executes the formal `gpt-5.5[extra_high]` ceiling probe across all included local tasks,
then runs a `gpt-5.4-mini[low]` floor probe and writes a combined report under
`results/shallowswe-codex-subscription-sizing-<stamp>/`.

Use `--ceiling-effort medium` only for a low-spend smoke pass. Medium smoke rows do not satisfy the
formal ceiling gate.

If a run was started before report semantics changed, regenerate the report without rerunning Pier:

```sh
uv run python scripts/run_codex_subscription_sizing.py \
  --report-only results/shallowswe-codex-subscription-sizing-<stamp>
```

The regenerated report treats only `gpt-5.5[extra_high]` as the formal ceiling calibration signal.
Medium or High rows remain smoke evidence only, even if an older run labeled them as ceiling rows.

To refresh live progress from existing Pier job directories:

```sh
uv run python scripts/run_codex_subscription_sizing.py \
  --progress-only results/shallowswe-codex-subscription-sizing-<stamp>
```

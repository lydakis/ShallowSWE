# ShallowSWE Build Plan

ShallowSWE is no longer in a pilot-only phase. This document tracks the path from the authored
36-task candidate matrix to a calibrated v1 benchmark.

The existing `py-normalize-username` task remains a harness smoke task and should not be counted as
benchmark evidence.

## Public Matrix

| Category | Small | Medium | Large |
| --- | --- | --- | --- |
| Code | local bug/test/fix | feature wiring or multi-file bug | multi-surface code behavior |
| Artifact | simple conversion/extraction | report/join with rejects | migration or multi-output package |
| Workflow | small repo/API action | config/git/tool chain | stateful repo/API reconciliation |

Target: 4 accepted tasks per cell, 36 tasks total.

The concrete v1 candidate set lives in `docs/v1-task-matrix.md`.

## Current Inventory

The repository has 36 authored official candidate tasks: 4 tasks in each `category x size` cell.
`py-normalize-username` remains smoke-only and is excluded from the matrix.

Most tasks are still candidates because final size assignment requires the empirical
floor-selection sweep and pinned-ceiling calibration in `docs/calibration-protocol.md`. Existing
historical calibration data remains useful, but old T4 labels are not part of the public taxonomy.

## Gates Before Acceptance

Before a task enters a publish snapshot:

1. Check `docs/task-selection-rubric.md` for realism and taxonomy fit.
2. Check `docs/verifier-contract.md` for deterministic scoring quality.
3. Run the verifier against the base repo and confirm it fails for the intended reason.
4. Run the reference solution three clean times.
5. Run at least one materially different alternate solution.
6. Run the floor-selection sweep, then pinned-ceiling/selected-floor calibration.
7. Record pass counts, rollouts, turns, tokens, measured attempt cost, CPSC, and uncertainty.

## Calibration Runs

Use `panels/shallowswe-calibration-v0.1.json`, not the publish panel, for floor selection. Run
enough cheap candidate rollouts for coarse size bands and keep those calibration rollouts out of
published leaderboard stats.

Budget the 36-task floor-selection sweep before running it:

```sh
uv run shallowswe estimate-panel panels/shallowswe-calibration-v0.1.json \
  --prices prices/openrouter-2026-07-03.json \
  --task-count 36 --rollouts 10 \
  --input-tokens 150000 --output-tokens 8000 --cache-read-tokens 100000 \
  --max-budget-usd 500 --fail-over-budget
```

Suggested floor-selection shape:

```sh
uv run pier run -p tasks \
  --include-task-name <task-id> \
  --agent mini-swe-agent \
  --model openrouter/moonshotai/kimi-k2.7-code \
  --model openrouter/z-ai/glm-5.2 \
  --model openrouter/google/gemini-3.5-flash \
  --agent-kwarg max_tokens=2048 \
  --agent-kwarg config_file=configs/mini-swe-agent-calibration.yaml \
  --env docker \
  --env-file /Users/lydakis/Developer/blue/apps/supervisor/.env.local \
  --agent-env 'OPENROUTER_API_KEY=${OPENROUTER_API_KEY}' \
  --job-name shallowswe_floor_selection_v1 \
  --jobs-dir /tmp/shallowswe-pier -n 3 -k 10 -q --yes
```

Keep concurrency conservative on local Docker. Higher values can exhaust Docker's predefined
network address pools before model calibration starts.

After a floor-selection run, export and summarize the measured floor candidates:

```sh
uv run shallowswe export-pier /tmp/shallowswe-pier/shallowswe_floor_selection_v1 \
  --tasks-root tasks > /tmp/shallowswe-floor-selection.json

uv run shallowswe select-floor /tmp/shallowswe-floor-selection.json \
  --saturation-threshold 0.85 > /tmp/shallowswe-floor-report.json
```

The report recommends the non-saturated pair with the widest task pass-rate spread and records
large-band task counts for audit.

## Build Order

1. Finish local verifier validation for all 36 candidate tasks.
2. Run floor selection and choose the primary floor-probe configuration by dynamic range, not by
   price.
3. Run the pinned ceiling and selected floor at calibration N for every task.
4. Move or reshape tasks that land outside their measured size band.
5. Convert remaining static hidden fixtures to seeded generators where the verifier computes the
   expected output internally.
6. Gate the bounded repair-loop pilot with:

   ```sh
   uv run shallowswe repair-loop-pilot-plan configs/shallowswe-repair-loop-pilot-v0.1.json
   ```

   Do not run a paid repair-loop pilot until this reports `ready_for_final_protocol_pilot = true`.
   The current plan passes this gate through the local `lydakis/mini-swe-agent` fork and the
   `shallowswe-resumable-mini-swe-agent` Pier import-path agent.
7. Recompute the workload index after the calibrated task set freezes.

## Publication Metrics

- Headline: CPSC by `(model, effort)` pair, category, and size.
- Diagnostics: solve rate, absolute loop cost per task, verifier submissions, cap hits, token
  counts, and turns.
- Intervals: Wilson intervals for solve rates and bootstrap intervals for CPSC.
- Price basis: raw repair-loop tokens plus a dated price table.

## Stop Conditions

- Do not run broad publish panels without a budget preflight.
- Do not accept tasks that require cleverness, hidden inference, external knowledge, or subjective judging.
- Do not let any hidden verifier assertion exceed the prompt or existing repo contract.
- Do not fill the suite with only code tasks; artifact and workflow are load-bearing.

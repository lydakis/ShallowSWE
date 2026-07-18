# ShallowSWE Calibration Protocol

> **Pre-v0.4.2 implementation history.** The active calibration contract is
> `docs/white-paper-v0.4.2.md` plus `docs/six-task-pilot-protocol-v0.3.md`. Size bands, old model
> identities, and fixed preview limits below are superseded and cannot launch official pilot rows.

This document defines how a candidate task becomes part of a calibrated ShallowSWE snapshot.

The short version:

```text
The ceiling defines what is shallow.
One-shot runs define task acceptance and size calibration.
Repair-loop runs define final CPSC.
Measured repair-loop cost defines single-model reliability-cost crossovers.
```

## V1 Task Funnel

The next v1 phase is task calibration, not broader leaderboard scoring. The v0.2 repair-loop
preview proved the basic cost-per-success thesis, but another large scoring run over the same
mostly-easy distribution would mostly buy tighter error bars on a known shape. Before spending on a
larger scoring panel, ShallowSWE should admit and size tasks through a task funnel.

The operating sequence is:

```text
1. Author candidate tasks, skewed toward medium/large hypotheses.
2. Run cheap one-shot triage to find obvious smalls, duplicates, broken prompts, and brittle
   verifiers.
3. Run a practical frontier screen to find candidates that are likely ceiling-solvable.
4. Run the formal ceiling gate only on serious survivors.
5. Run bridge validation in the actual scoring harness before accepting labels.
6. Freeze the v1 task suite and scoring panel.
7. Seek or allocate funding/credits for N=10 repair-loop scoring.
8. Run broad scoring only after task distribution is fixed.
```

Codex subscription capacity may be used to accelerate authoring and triage, but it is not
publishable calibration ground truth unless it is the same scaffold, prompt, verifier loop, and
versioned `model_config` used by the scoring run. Any candidate accepted through Codex-assisted
triage needs a bridge check in the real Pier/mini-swe scoring harness before its calibrated label is
treated as official.

For this v1 tranche, the formal ceiling is `openai/gpt-5.5[extra_high]`. `openai/gpt-5.5[medium]`
may be used only as a cheap smoke screen to expose ambiguity, packaging bugs, or obviously broken
verifiers. A Medium pass is not ceiling evidence, and a Medium failure is not an admission failure
until the task has been reviewed and, if still viable, tested against the Extra High ceiling.

The immediate authoring target is one medium/large-heavy tranche of 12-20 new candidates. If the
funnel works, scale toward a larger candidate pool. The final v1 target remains 36 calibrated tasks,
but the accepted pool should be larger than 36 before final selection so easy, duplicated, too-hard,
or ambiguous tasks can be discarded without weakening the matrix.

Each candidate ends in exactly one task-funnel bucket:

| Bucket | Meaning | Action |
| --- | --- | --- |
| Keep small | Floor passes often enough to be a control or high-volume routine task | Keep only enough to fill small cells |
| Keep medium | Floor one-shot behavior lands in the medium band and ceiling is strong | High-value candidate |
| Keep large | Floor one-shot behavior lands in the large band, repair loops should matter, and ceiling is strong | Highest-value candidate |
| Too easy / duplicate | Models first-submit it too often or it adds little new work shape | Archive or keep as smoke-only |
| Bad task | Ceiling struggles, verifier is brittle, prompt is ambiguous, or difficulty is artificial | Fix or discard |

The next public scientific artifact should be the v1 task calibration report: how candidate routine
SWE tasks were filtered into the calibrated suite by frontier ceiling probes, cheap-floor probes,
bridge-harness validation, and verifier review. A new leaderboard should follow that report, not
precede it.

Use the machine-readable task-funnel ledger to keep this phase auditable:

```text
uv run shallowswe task-funnel configs/shallowswe-v1-task-funnel-tranche-1.json
```

The ledger may track planned tasks that do not exist yet, authored probes, provisional Codex
subscription triage, formal ceiling status, and bridge-validation status. A task is not an official
calibrated label until the ledger shows it survived the required formal ceiling and bridge checks.

## Core Rule

Difficulty is expressed in two layers: one-shot first-submit behavior is the acceptance and
calibration signal, and bounded repair-loop behavior is the final scoring signal.

- **Pinned ceiling**: the pre-registered frontier `model_config` used to decide whether a task is
  within reach of current frontier agents. The formal ceiling may use a higher reasoning effort
  than the default scoring panel because it is an admission judge, not a leaderboard row. One-shot
  is the task acceptance gate because repair loops can converge and hide task-difficulty
  differences. Operationally, pre-register a ceiling one-shot threshold for the snapshot. `>=75%` is the v1
  candidate threshold. At `N=16`, that means `12/16` accepts, `11/16` investigates, and `<=10/16`
  fixes or evicts.
- **Dialed floor**: small, medium, and large are assigned by first-submit floor behavior plus
  authoring surface. Repair-loop solve rate is not an acceptance criterion because models can
  converge after feedback. Do not size by LOC, fixture size, or author intuition except as a pre-run
  hypothesis.
- **Independent ceiling audit**: before evicting a task the primary ceiling fails, optionally run
  one other frontier pair as a separate one-shot diagnostic. If both fail, evict or redesign. If
  only the primary ceiling fails, fix the prompt/verifier ambiguity or record a model-specific
  quirk before rerunning. This audit is never a fallback, cascade, scored substitute, or
  continuation of the primary model's sandbox.

The old T4/shelf-edge label is historical only. Large tasks are ordinary ShallowSWE tasks that
create enough convergence pressure to make cost and cap-hit differences visible.

Current one-shot runs are calibration and admission evidence. They are useful for first-submit
reliability, task acceptance, prompt/verifier triage, and sorting tasks into easy/mixed/hard
buckets. They are not final CPSC scoring; final ShallowSWE CPSC is measured from bounded repair
loops.

## Calibration Panels

The panel unit is a `model_config`, defined as `(model, effort, sampling_config)`. A model at low
effort and the same model at medium or high effort are separate cost/reliability points. Effort
rungs are treated the same way as cross-model rungs in reliability-cost analysis.

Each snapshot has two pre-registered calibration panels:

- `ceiling_panel`: frontier `model_config`s used only to decide whether a candidate task is
  admissible for the snapshot.
- `floor_probe_panel`: cheaper or lower-effort `model_config`s used to assign task size.

The ceiling and floor-probe panels are frozen before suite authoring and task admission. The
broader published leaderboard panel may be frozen later, before the full published repair-loop run.

The ceiling panel is evaluated as an admission instrument, not as a scored economic configuration.
Use cheap and practical frontier screens for triage, then spend the formal ceiling only on serious
survivors. If the formal ceiling cannot clear the gate, the task is too hard for the snapshot or has
a prompt/verifier flaw. If a practical medium/high screen fails but the formal ceiling passes, the
task may still be a good medium or large candidate. A candidate task is admitted if at least one
`ceiling_panel` config clears the pre-registered one-shot gate and verifier review finds no task
flaw. For v1, that gate is `>=75%` over `N=16`, or at least `12/16` successful one-shot runs.

The exact ceiling is a frozen `model_config`, not a marketing label. If the chosen frontier model is
selected through Codex or another subscription surface, record the actual backend, effort setting,
sampling config, scaffold, and date. If the scoring run uses API/OpenRouter/Pier instead, bridge
accepted tasks through that same scoring harness before treating Codex-derived labels as official.

The primary floor-probe configuration is chosen by measurement, not by price. Secondary floor-probe
configs are recorded for sensitivity analysis and trigger manual review if they disagree with the
primary assignment by more than one size band. A cheap pair that rarely fails is a mid rung, not the
floor.

## Floor Selection

Before assigning final sizes, run a cheap floor-selection sweep:

1. Use the 36 authored and locally validated candidate tasks.
2. Run 3-4 cheap candidate pairs in one-shot mode to find first-submit dynamic range.
3. Pick the primary floor-probe configuration with the widest useful first-submit spread.
4. Use repair-loop probes only to estimate final scoring behavior and cap settings, not task
   admission.
5. If a cheap pair passes nearly everything, keep it as a mid reliability-cost rung instead of the
   floor.

The floor must show meaningful one-shot failures on some large tasks. Otherwise CPSC stops doing
work and the benchmark collapses into a pricing table.

## Size Bands

Bands are one-shot calibration bands, not final scoring bands.

| Size | Role | Floor one-shot band | Ceiling one-shot gate |
| --- | --- | ---: | --- |
| Small | Control tasks and high-volume routine work | 70-100% | pre-registered, v1 candidate >=75% |
| Medium | Routine delegated chunks | 30-70% | pre-registered, v1 candidate >=75% |
| Large | Crossover and convergence-pressure tasks | 0-40% | pre-registered, v1 candidate >=75% |

If a task lands outside its hypothesized band, move it or reshape it. Do not keep an incorrect size
label because the author intended it. Repair-loop spend, verifier submissions, and cap-hit rate are
reported in final results, but they do not decide task admission.

## Reshaping Rules

Prefer levers that lower floor first-submit reliability while preserving the ceiling one-shot gate:

- more entry points that must stay consistent,
- more local repo context around a small relevant change,
- state reconciliation with idempotency and preservation requirements,
- deterministic retry or recovery behavior,
- larger but still explicit artifact packages.

Avoid levers that break the ceiling:

- ambiguous product judgment,
- hidden requirements,
- obscure algorithms,
- current events or external services,
- exact implementation shape not stated by the prompt or existing API.

## Repair-Loop Protocol

For each task/model_config/seed:

```text
1. Start from a clean sandbox.
2. Agent works normally: reads files, edits code, runs visible tests/tools.
3. Agent declares done.
4. Harness runs the hidden verifier.
5. If verifier passes: task is successful, stop.
6. If verifier fails: tell the agent limited feedback and continue in the same context.
7. Repeat until success or a cap is hit.
```

Allowed hidden-verifier feedback is limited to:

```text
Verification failed. Continue working.
Verification failed: runtime error.
Verification failed: missing required artifact.
Verification failed: output mismatch.
Verification passed.
```

Do not expose hidden assertion messages, expected hidden outputs, hidden input fixture values,
golden diffs, hidden verifier line numbers, or full hidden stdout/stderr when it reveals the
answer. Visible test, compiler, linter, runtime, and script output generated by the agent remains
allowed.

Stop at first pass, or when any cap is hit:

- dollar cap,
- verifier-submission cap,
- wall-time cap,
- agent-step cap.

Dollar caps are safety limits, not intended difficulty controls. They must be high enough that
ceiling models rarely hit them during calibration. Verifier-submission caps prevent probing the
hidden verifier. Step caps prevent indefinite loops. Wall-time cap is an infra guard, not a scored
differentiator; retry it as an excluded infra row unless the step cap corroborates a genuine loop.

### Single-Model Run Invariant

Every scored repair-loop run is bound to exactly one `model_config`. All agent turns, repair-loop
continuations, verifier-feedback responses, and cap outcomes within that row use the same
`model_config`. ShallowSWE does not use model fallback, escalation, ensembling, judge models,
retrying with a different model, or transcript handoff to another model inside a scored run. If the
model fails, hits a cap, or exhausts context after meaningful work starts, that row records the
failure for that same `model_config`.

## Cost Accounting

Repair-loop rows store tokens, stop reason, verifier submissions, and status. Dollars are a
rendered view produced from a versioned price table.

The core metric is:

```text
CPSC = total model spend across scored repair-loop rows / number of successful repair loops
```

Failed verifier submissions, extra turns, and cap-hit final failures count in total spend. Provider,
network, credential, credit, model-resolution, provider-dispatch, verifier-infrastructure failures,
and wall-time infra guards are excluded and retried. Model failures inside the task are scored.
Context exhaustion after meaningful agent progress is scored. Context exhaustion caused by task
packaging, prompt construction, provider dispatch mismatch, or scaffold overhead before meaningful
work begins is excluded and fixed.

CPSC is computed per `model_config`; no scored row combines spend from multiple models.

Aggregation cells with zero successful repair loops have undefined CPSC and are reported as "no
verified successes"; their failed-loop spend is still shown.

Raw token counts are useful per-model diagnostics. Cross-model comparisons use measured loop spend
because tokenizers and provider accounting differ.

## Single-Model Reliability-Cost Frontier

ShallowSWE v1 does not use fallback models. Each repair-loop run uses exactly one `model_config`.
If the model fails or hits a scored cap, that row is a failed row for that model; no frontier model
inherits the sandbox, patch, or transcript.

The publish chart should rank single `model_config` rows by measured repair-loop cost per
successful completion and solve-rate confidence intervals. A row is eligible for recommendation
only if it clears the snapshot's declared solve-rate floor. For the hero frontier, solve-rate
eligibility is computed over the category/size slice using the snapshot's declared task weights.
The v1 default floor is 90% scored repair-loop solve rate. Cheap models may flail through several
verifier submissions or hit caps, so list-price ratios and one-shot attempt costs are not
sufficient.

If no row in a category/size slice reaches 90%, the chart displays "no recommended configuration"
and shows the cheapest rows within two percentage points of the best observed solve rate as
diagnostics only. Eligible rows are ranked by point-estimate CPSC. If the cheapest eligible row's
CPSC interval overlaps another eligible row's interval, the UI labels them "statistically tied" and
displays both. The primary recommendation remains the lowest point estimate unless a conservative
view is selected.

A frontier cell is disputed if the cheapest eligible row's CPSC confidence interval overlaps
another eligible row's interval, or if another eligible row is within 10% of its point-estimate
CPSC. In disputed cells, all overlapping or near-frontier rows are rerun to `N=20`, and the `N=20`
results replace `N=10` for that displayed comparison. If a recommended row clears the slice-level
floor but has any task below 60% solve rate, the UI marks it "slice-aggregate only" rather than
implying reliable performance on every task shape.

The primary published artifact should be a single-model reliability-cost frontier chart by category
and size, backed by CPSC, solve-rate, verifier-submission, and cap-hit tables. The leaderboard is
secondary. The benchmark answers which `model_config` should be chosen up front for a kind of work,
not which model is globally best.

The benchmark assumes free and perfect hidden verification because task verifiers are oracle
programs. Production verification has cost and false negatives. ShallowSWE therefore measures an
upper bound on savings from up-front single-model selection.

## Statistical Requirements

Calibration and publish runs must show uncertainty.

- Plumbing probes use `N=1`.
- Task-admission one-shot ceiling gates use `N=16` per primary ceiling config.
- Size-calibration floor probes use `N=10` per floor config.
- Published scoring uses `N=10` repair-loop seeds per task/model_config.
- Report-grade reruns for disputed frontier cells use `N=20` for every overlapping or near-frontier
  row, not only the apparent winner.
- Primary uncertainty intervals bootstrap over tasks within each category/size slice. Seed-level
  variation is reported as secondary stochasticity; seeds do not replace task diversity.
- Report Wilson intervals for solve rates.
- Report bootstrap intervals for repair-loop CPSC.
- Report average verifier submissions to success and cap-hit rate.
- Display adjacent leaderboard rows as tied when CPSC intervals overlap.

Small-N probes are useful for plumbing and triage, but they do not assign final size.

## Snapshot Admission

A task can enter a calibrated snapshot only after:

1. The base fixture fails for the intended fail-to-pass reason.
2. The reference solution passes cleanly and deterministically.
3. At least one materially different alternate solution passes.
4. Prompt-verifier alignment review finds no hidden requirement.
5. At least one pre-registered ceiling `model_config` clears the one-shot acceptance gate and
   verifier review finds no task flaw.
6. The selected floor-probe configuration places the task in one of the size bands by one-shot
   behavior.
7. Repair-loop smoke confirms the task can be scored under the final protocol without leaking
   verifier answers.
8. The task metadata or calibration evidence records the snapshot id, ceiling panel, ceiling
   one-shot seed count and pass counts, floor panel, floor one-shot seed count and pass counts,
   admission decision, size-assignment decision, repair-loop smoke evidence, cap settings, and
   price-table version used for any dollar rendering.

If any of these are missing, the task is a candidate or locally validated task, not an official
calibrated task.

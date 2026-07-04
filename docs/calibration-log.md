# ShallowSWE Calibration Log

Calibration runs decide size assignment and acceptance. They are not published leaderboard rollouts.

Taxonomy note: entries from 2026-07-03/04 use the old T1-T4 naming. The active public taxonomy is
now `category = code|artifact|workflow` and `size = small|medium|large`; old T4 candidates are
interpreted as large tasks, not a special benchmark tier.

## 2026-07-04: 36-task local verifier validation

Purpose: validate the authored v1 candidate matrix before spending on model calibration.

Run shape:

```text
tasks: 36 official tasks, excluding py-normalize-username smoke
environment: docker
reference check: pier oracle agent, N=1 per task
base check: pier nop agent, N=1 per task
artifacts:
  /tmp/shallowswe-pier/shallowswe_local_oracle_36/result.json
  /tmp/shallowswe-pier/shallowswe_local_nop_36/result.json
```

Results:

| Check | Trials | Exceptions | Passes | Mean reward |
| --- | ---: | ---: | ---: | ---: |
| Reference solution via `oracle` | 36 | 0 | 36 | 1.000 |
| Unmodified base via `nop` | 36 | 0 | 0 | 0.000 |

Decision:

The 36-task matrix is locally validated for reference-solution packaging and base-failure behavior.
This does not assign final sizes. Final small/medium/large labels still require the floor-selection
sweep and pinned-ceiling calibration in `docs/calibration-protocol.md`.

## 2026-07-04: OpenRouter plumbing probes

Purpose: verify that the OpenRouter env-file path, mini-swe-agent kwargs, and Docker execution work
before a high-N calibration run.

Results:

- Single-task capped probe: `env-flags-to-json` with `moonshotai/kimi-k2.7-code` passed 1/1 with
  no exceptions in 1m23s.
- Full-matrix N=1 probe at local Docker concurrency 10 was stopped after Docker infrastructure
  errors: `all predefined address pools have been fully subnetted`.
- Full-matrix N=1 probe at local Docker concurrency 3 was stopped after a rejected v3 protocol
  experiment. It completed 19 trials, had 3 errored/cancelled trials, left 89 pending, and spent
  about `$1.78`. Partial stats showed useful spread, but the run was interrupted before covering the
  task matrix.
- A later v3 experiment with an added Laguna row was stopped at 16/144 completed trials after the
  margin metric was rejected. It spent about `$1.53`. This is recorded as discarded exploratory
  evidence, not calibration.
- After reverting to the v2 protocol, a full-matrix N=1 floor probe at local Docker concurrency 3
  was stopped when Docker image builds ran out of local space. It completed 47 trial directories,
  exported 38 scored rows and 9 `runner_infrastructure_error` exclusions, left 61 trials pending,
  and spent about `$2.78`. The partial scored rows showed the desired rough gradient:
  `small = 1.0`, `medium = 0.25-0.40`, `large = 0.33-0.50` across the three cheap panel rows.
  Because coverage is incomplete and failures were runner infrastructure failures, this is
  plumbing and floor-shape evidence only.

Decision:

Do not treat interrupted N=1 runs as calibration evidence. Use
`configs/mini-swe-agent-calibration.yaml`, local Docker concurrency no higher than 3, and the v2
floor-selection procedure before assigning final sizes.

## 2026-07-04: v2 floor-shape probe, N=1 complete

Purpose: complete a cheap full-matrix floor-shape pass after rejecting v3 and before spending on
high-N floor calibration.

Run shape:

```text
tasks: 36 official tasks, excluding py-normalize-username smoke
agent: mini-swe-agent
environment: docker
local concurrency: 3
attempts per cheap panel row: 1
max_tokens: 2048
config: configs/mini-swe-agent-calibration.yaml
artifacts:
  results/shallowswe-floor-probe-n1-v2-2026-07-04/pier-result.json
  results/shallowswe-floor-probe-n1-v2-2026-07-04/rollouts.json
  results/shallowswe-floor-probe-n1-v2-2026-07-04/floor-selection-report.json
```

The job was resumed twice after Docker build cache pressure caused apt package-install failures.
After pruning Docker build cache and retrying only failed infrastructure trials, the final export
contains 108 scored rows, 0 exclusions, 0 exceptions, and about `$6.34` of gateway-reported spend.

| Candidate floor row | Scored rows | Passes | Pass rate |
| --- | ---: | ---: | ---: |
| `google/gemini-3.5-flash` | 36 | 21 | 0.583 |
| `moonshotai/kimi-k2.7-code` | 36 | 22 | 0.611 |
| `z-ai/glm-5.2` | 36 | 23 | 0.639 |

The v2 floor selector recommends `google/gemini-3.5-flash` at this N=1 stage because it is the
weakest non-saturated row with full matrix coverage.

Selected-floor pass rates by hypothesized size:

| Size | Gemini pass rate |
| --- | ---: |
| Small | 0.667 |
| Medium | 0.583 |
| Large | 0.500 |

Selected-floor pass rates by category and size:

| Cell | Gemini pass rate |
| --- | ---: |
| `artifact/large` | 0.250 |
| `artifact/medium` | 0.250 |
| `artifact/small` | 0.500 |
| `code/large` | 1.000 |
| `code/medium` | 1.000 |
| `code/small` | 1.000 |
| `workflow/large` | 0.250 |
| `workflow/medium` | 0.500 |
| `workflow/small` | 0.500 |

Interpretation:

This is a valid floor-shape probe, not final calibration. It proves the 36-task set has real
cheap-row failure signal and that `google/gemini-3.5-flash` is the provisional floor candidate.
It also shows the hypothesized size labels are not calibrated yet: small tasks are too hard for the
selected floor, especially artifact and workflow small tasks. Before high-N final size assignment,
either reshape/relabel those small artifact/workflow tasks or select a stronger floor pair and
rerun the sweep.

N=1 reshape queue before high-N calibration, based on the pre-fix full probe:

- Too easy or saturated under all three cheap rows: all 12 code tasks passed for all three rows.
  Keep some as small controls, but harden or relabel code medium/large before using code size bands
  as final evidence.
- Too hard for hypothesized small: `spec-to-release-checklist`, `post-build-status`, and
  `ticket-cut-from-bug-report` failed all three cheap rows; `env-flags-to-json` failed the
  provisional floor. Simplify, relabel upward, or swap these out of small before high-N.
- Artifact medium is currently closer to large: `access-log-to-incidents`,
  `markdown-table-inventory`, and `subscription-summary-report` failed all three cheap rows; only
  `payout-reconcile` passed a majority of cheap rows.
- Workflow medium is split: `config-flag-ignored` and `dependency-api-rename` passed all three rows,
  while `release-branch-cherry-pick` and `ticket-update-dont-duplicate` failed all three. This cell
  needs either relabeling or task reshaping before high-N.
- Large artifact/workflow tasks produce useful failures, but `ledger-schema-upgrade` and
  `ticket-state-reconcile` are saturated at N=1 and should not be relied on as large unless high-N
  floor results contradict the probe.

## 2026-07-04: v2 small-task prompt/verifier audit

Purpose: fix small-task failures that came from hidden conventions or self-test traps rather than
real task difficulty.

Changes:

- `env-flags-to-json`: moved the visible input from hidden `input/.env.local` to
  `input/flags.env`, so normal file discovery surfaces the input. The hidden verifier still reruns
  the parser on a fresh `input/flags.env` with different values.
- `spec-to-release-checklist`: made sequential `rel-1`, `rel-2`, ... IDs and field derivation
  explicit in the visible prompt.
- `ticket-cut-from-bug-report`: made exact ticket fields and exact call-log output explicit in the
  visible prompt.
- `post-build-status`: made exact status fields explicit and changed the prompt from append
  semantics to write-exactly-one semantics. This removes a verifier trap where an agent that
  self-tested the script could create duplicate visible state before the verifier reran it.

Local verifier checks:

| Probe | Tasks | Oracle | Nop | Exceptions |
| --- | ---: | ---: | ---: | ---: |
| initial four-task prompt fix | 4 | 4/4 | 0/4 | 0 |
| workflow schema tightening | 2 | 2/2 | 0/2 | 0 |
| final post-status overwrite fix | 1 | 1/1 | 0/1 | 0 |

Targeted cheap-panel reruns:

| Probe artifact | Rows | Passes | Exclusions | Gateway spend | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `results/shallowswe-floor-probe-n1-v2-promptfix-4-2026-07-04/` | 12 | 9 | 0 | `$0.4534` | `env-flags-to-json` and `spec-to-release-checklist` became 3/3; workflow tasks still exposed schema issues. |
| `results/shallowswe-floor-probe-n1-v2-promptfix2-workflow-2026-07-04/` | 6 | 3 | 0 | `$0.2306` | `ticket-cut-from-bug-report` became 3/3; `post-build-status` exposed append/self-test mismatch. |
| `results/shallowswe-floor-probe-n1-v2-promptfix3-post-2026-07-04/` | 3 | 3 | 0 | `$0.1135` | `post-build-status` became 3/3 after write-exactly-one semantics. |

Current result after prompt/verifier audit:

| Task | Targeted post-fix cheap-panel result |
| --- | ---: |
| `env-flags-to-json` | 3/3 |
| `spec-to-release-checklist` | 3/3 |
| `ticket-cut-from-bug-report` | 3/3 |
| `post-build-status` | 3/3 |

Interpretation:

These four tasks now behave like small controls at N=1 across the cheap calibration panel. This
does not assign final size bands; it removes prompt/verifier ambiguity before the next full-matrix
or high-N floor calibration run. The pre-fix full N=1 pass rates for these tasks should be treated
as diagnostic evidence, not current task difficulty.

## 2026-07-03/04: `ledger-schema-upgrade`

Purpose: test whether the first transform shelf-edge candidate qualifies as T4 under
`panels/shallowswe-calibration-v0.1.json`.

Run shape:

```text
task: ledger-schema-upgrade
agent: mini-swe-agent
environment: docker
attempts per anchor row: 15
max_tokens: 4096
calibration artifacts: results/shallowswe-t4-ledger-calibration-2026-07-03/
```

| Anchor row | Effort | Passes | Attempts | Pass rate | CPSC | Runtime |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `z-ai/glm-5.2` | high | 12 | 15 | 0.800 | 0.0775 | 27m 47s |
| `google/gemini-3.5-flash` | medium | 13 | 15 | 0.867 | 0.6445 | 51m 55s |
| `moonshotai/kimi-k2.7-code` | default | 14 | 15 | 0.933 | 0.1514 | 1h 27m 19s |

Panel summary:

- Median anchor pass rate: 0.867.
- Weakest anchor pass rate: 0.800.
- Excluded attempts: 0.
- T4 gate: failed. The T4 median band is 0.300-0.700.
- T3 gate: passed. The T3 median band is 0.800-0.950.

Decision:

`ledger-schema-upgrade` is not accepted as T4. It is marked `calibrated_t3` in task metadata and
should be treated as a high-T3 deterministic transform task unless it is redesigned into a harder
candidate and recalibrated.

Interpretation:

The N=1 expanded-panel failure by Gemini 3.5 Flash medium was a sizing signal, not a stable tier
assignment. At N=15, all three cheap anchor rows clear at least 80%, so this task is below the
shelf-edge failure band even though it remains useful for measuring flailing, token cost, and
retry tax.

## 2026-07-03: `config-key-rollover`

Purpose: validate T4 packaging and Pier/OpenRouter plumbing on a cross-cutting operate task.

Result:

- N=1 expanded-panel sweep passed 10/10 model configs.
- No high-N shelf-edge calibration was run after saturation.
- The task remains a plumbing probe with `probe_saturated_n1` metadata.

Decision:

`config-key-rollover` is not accepted as T4 without redesign. It may be demoted or kept as an
internal probe.

## 2026-07-03/04: `status-terminal-parity`

Purpose: test whether a multi-entry status-parity fix creates enough shelf-edge pressure for T4.

Run shape:

```text
task: status-terminal-parity
agent: mini-swe-agent
environment: docker
attempts per anchor row: 1
max_tokens: 4096
calibration artifacts: results/shallowswe-t4-status-calibration-2026-07-03/
```

| Anchor row | Effort | Passes | Attempts | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `z-ai/glm-5.2` | high | 1 | 1 | 1.000 | 0.0233 | 10 |
| `google/gemini-3.5-flash` | medium | 1 | 1 | 1.000 | 0.3019 | 31 |
| `moonshotai/kimi-k2.7-code` | default | 1 | 1 | 1.000 | 0.0568 | 17 |

Decision:

`status-terminal-parity` is not accepted as T4 without redesign. It is marked
`probe_saturated_n1`. Gemini's 31-turn pass is useful flailing evidence, but the candidate is too
solvable on first attempt to justify immediate N=15 T4 calibration.

## 2026-07-04: `ticket-state-reconcile`

Purpose: test whether deterministic local API reconciliation creates a real shelf-edge T4 task.

Run shape:

```text
task: ticket-state-reconcile
agent: mini-swe-agent
environment: docker
anchor attempts per row: 15
top-gate attempts: 5
max_tokens: 4096
calibration artifacts: results/shallowswe-t4-ticket-calibration-2026-07-03/
```

Cheap-anchor calibration:

| Anchor row | Effort | Passes | Attempts | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `google/gemini-3.5-flash` | medium | 5 | 15 | 0.333 | 1.5428 | 22.1 |
| `z-ai/glm-5.2` | high | 6 | 15 | 0.400 | 0.1548 | 9.5 |
| `moonshotai/kimi-k2.7-code` | default | 10 | 15 | 0.667 | 0.2193 | 18.4 |

Top-gated calibration:

| Top row | Effort | Passes | Attempts | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `openai/gpt-5.5` | medium | 5 | 5 | 1.000 | 0.4489 | 13.6 |

Publish-panel top-up:

The expanded publish panel was topped up on this task on 2026-07-04 so the Claude/OpenAI rows
have N=5 scored attempts. These rows are publish data, not a new calibration gate. Three
provider/network retry exclusions are retained separately in the public rollouts.

| Publish row | Effort | Passes | Scored attempts | Excluded | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `anthropic/claude-fable-5` | low | 4 | 5 | 0 | 0.800 | 0.4603 | 7.0 |
| `anthropic/claude-opus-4.8` | low | 3 | 5 | 1 | 0.600 | 0.3503 | 9.0 |
| `anthropic/claude-opus-4.8` | medium | 5 | 5 | 0 | 1.000 | 0.3524 | 10.4 |
| `anthropic/claude-sonnet-5` | low | 2 | 5 | 0 | 0.400 | 0.2312 | 7.4 |
| `anthropic/claude-sonnet-5` | medium | 4 | 5 | 0 | 0.800 | 0.1811 | 9.2 |
| `openai/gpt-5.5` | low | 5 | 5 | 2 | 1.000 | 0.2956 | 10.0 |

Panel summary:

- Median anchor pass rate: 0.400.
- Weakest anchor pass rate: 0.333.
- Top-gated pass rate: 1.000.
- T4 gate: passed. The calibration-panel median is inside the 0.300-0.700 T4 band, and the
  top-gated row clears the >=0.800 gate.

Decision:

`ticket-state-reconcile` is retained as a calibrated large workflow task. It enters the same
benchmark basket through the `workflow` category and `large` size band; the old T4 label remains
calibration history only.

Interpretation:

This task demonstrates the second cost mechanism. Small and medium saturation can still measure
flailing and context rent among successful rollouts, while large shelf-edge tasks expose the
retry-tax denominator: some rows are cheap per attempt but no longer cheap per success.

## 2026-07-04: v2 36-task post-fix floor probe

Purpose: validate the full v2 36-task matrix after prompt/verifier fixes, using a cheap N=1 floor
probe before any high-N benchmark run.

Run shape:

```text
tasks: 36 official tasks, excluding py-normalize-username smoke
agent: mini-swe-agent
environment: docker
attempts per cheap row: 1
cheap rows:
  - google/gemini-3.5-flash
  - moonshotai/kimi-k2.7-code
  - z-ai/glm-5.2
default config: configs/mini-swe-agent-calibration.yaml
status recovery config: configs/mini-swe-agent-calibration-long.yaml
combined artifacts: results/shallowswe-floor-probe-n1-v2-postfix-2026-07-04/
```

The first full-matrix run completed but was diagnostic only because Docker image builds ran out of
space during later tasks. The affected task rows were recovered with lower concurrency after Docker
cleanup. The final combined artifact keeps the unaffected diagnostic rows and replaces exactly these
nine affected task rows:

- `billing-revenue-rollup`
- `cache-invalidates-on-settings-change`
- `date-window-inclusive`
- `env-flags-to-json`
- `markdown-table-inventory`
- `report-json-format`
- `settings-null-default`
- `status-terminal-parity`
- `subscription-summary-report`

The combined result has 108 scored rows, 36 tasks, 3 model rows per task, and no excluded rows.

Overall cheap-row results:

| Floor row | Passes | Attempts | Pass rate | Small | Medium | Large |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `google/gemini-3.5-flash` | 24 | 36 | 0.667 | 1.000 | 0.583 | 0.417 |
| `moonshotai/kimi-k2.7-code` | 25 | 36 | 0.694 | 1.000 | 0.500 | 0.583 |
| `z-ai/glm-5.2` | 26 | 36 | 0.722 | 1.000 | 0.583 | 0.583 |

Category/size shape:

| Category / size | Gemini | Kimi | GLM |
| --- | ---: | ---: | ---: |
| artifact / small | 1.000 | 1.000 | 1.000 |
| artifact / medium | 0.250 | 0.000 | 0.250 |
| artifact / large | 0.250 | 0.250 | 0.250 |
| code / small | 1.000 | 1.000 | 1.000 |
| code / medium | 1.000 | 1.000 | 1.000 |
| code / large | 0.750 | 1.000 | 1.000 |
| workflow / small | 1.000 | 1.000 | 1.000 |
| workflow / medium | 0.500 | 0.500 | 0.500 |
| workflow / large | 0.250 | 0.500 | 0.500 |

The default 600-second wall-time cap remains appropriate for the floor probe. It prevents one row
from consuming the run when an agent keeps looping after it has enough information. The only
exception was `status-terminal-parity`: its Kimi row was interrupted under the 600-second cap after
passing local tests but continuing to inspect files. A targeted 1200-second recovery completed all
three status rows successfully in 11m03s. That justifies keeping the long cap as a targeted recovery
configuration, not as the default benchmark policy.

Decision:

This is acceptable v2 floor evidence for the current 36-task matrix, not final statistical
calibration. The small band is intentionally saturated and the medium/large bands now create a clear
cheap-model crossover region. `google/gemini-3.5-flash` is the selected cheap floor row for the next
calibration pass because it is non-saturated overall and has the lowest large-task pass rate.

Open calibration work:

- Run higher-N confirmation on the selected floor row before treating per-task failure rates as
  stable.
- Add or adjust a small number of medium/large code tasks if the next pass still shows code as too
  saturated relative to artifact and workflow tasks.
- Keep the v2 structure: task category plus size band. Do not reintroduce a separate T4 bucket or
  the rejected v3 margin metric.

What this run taught us:

- The task matrix has a real floor gradient. The selected cheap floor row, `google/gemini-3.5-flash`,
  passed 24/36 tasks overall, with small at 12/12, medium at 7/12, and large at 5/12.
- The small band is doing its intended control job. It is saturated across all three cheap rows.
- The medium/large bands are no longer price-sheet-only. They create cheap-model failures and
  therefore exercise the CPSC denominator.
- Artifact and workflow tasks are currently the strongest source of floor pressure. Code medium and
  code large are likely too easy if higher-N floor calibration confirms the N=1 shape.
- Ten tasks failed all three cheap rows at N=1. That is useful floor pressure only if the pinned
  ceiling passes them; otherwise they are ambiguous or too hard for ShallowSWE.
- `status-terminal-parity` showed why the default wall-time cap should remain. A targeted long-cap
  recovery passed, but the normal cap correctly exposed a slow/flailing row.
- Docker disk exhaustion can create false task failures. Broad runs should start with Docker cleanup
  and conservative concurrency, and recovery rows must be tracked separately from model failures.

## 2026-07-04: v2 admission audit and ceiling timing

Purpose: check task-local snapshot admission evidence before spending on broad high-N calibration.

Artifact:

```text
results/shallowswe-admission-audit-2026-07-04/admission-audit.json
results/shallowswe-admission-audit-2026-07-04/ceiling-smoke-estimate.json
```

Result:

- 36 official tasks were audited.
- 0/36 are ready for calibrated snapshot admission.
- Every official task is missing a materially different alternate solution artifact.

Decision:

The task set remains a candidate calibrated set with floor evidence, not a final calibrated
snapshot. The missing alternate-solution evidence blocks final admission even if model calibration
passes.

Ceiling timing:

1. Run an N=1 ceiling smoke using `panels/shallowswe-ceiling-v0.1.json` before high-N floor
   calibration. This is a cheap ambiguity detector, not final admission. The static estimate is
   $19.44 for the primary GPT-5.5 medium row alone, or $37.44 if both ceiling rows are run across
   every task.
2. Fix or evict any task that the primary ceiling fails at N=1. If needed, run the independent
   ceiling audit as a separate diagnostic before eviction. It is not a fallback and cannot turn the
   primary row into a pass.
3. After alternate-solution evidence exists and the task set freezes, run the pinned ceiling in
   one-shot mode at the pre-registered v1 gate: 75% pass rate, so `12/16` accepts, `11/16`
   investigates, and `<=10/16` fixes or evicts.
4. Only then treat the selected floor's high-N one-shot pass rates as final size assignments.
5. Run bounded repair-loop scoring only after the one-shot calibrated task set is accepted.

## 2026-07-04: v2 N=1 ceiling smoke

Purpose: run the cheap ambiguity detector before high-N floor calibration.

Artifacts:

```text
results/shallowswe-ceiling-smoke-gpt55-medium-n1-2026-07-04/rollouts.json
results/shallowswe-ceiling-second-opinion-opus48-medium-n1-2026-07-04/rollouts.json
results/shallowswe-ceiling-diagnosis-2026-07-04/ceiling-diagnosis.json
results/shallowswe-ceiling-diagnosis-2026-07-04/ceiling-failure-triage.json
```

Run shape:

```text
primary ceiling: openai/gpt-5.5, reasoning_effort=medium
independent ceiling audit: anthropic/claude-opus-4.8, reasoning_effort=medium
agent: mini-swe-agent
config: configs/mini-swe-agent-calibration.yaml
environment: docker
attempts per row: 1
primary tasks: 36 official tasks, excluding py-normalize-username smoke
audit tasks: 11 primary-ceiling failures only, run as fresh independent attempts
```

The audit artifact path uses the earlier `second-opinion` name, but those rows were independent
diagnostics. They did not inherit state from the primary run and did not count as fallback passes.

Results:

| Row | Tasks | Passes | Failures | Exceptions | Reported cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| `openai/gpt-5.5[medium]` primary | 36 | 25 | 11 | 0 | 6.6221 |
| `anthropic/claude-opus-4.8[medium]` independent audit | 11 | 0 | 11 | 0 | 1.2484 |

One-shot ceiling gate report:

```text
results/shallowswe-ceiling-diagnosis-2026-07-04/one-shot-ceiling-gate.json
```

Gate shape:

```text
mode: one-shot calibration/admission
threshold: 75%
target rollouts: 16
accept: 12/16
investigate: 11/16
fix or evict: <=10/16
```

Current GPT-5.5 medium N=1 diagnostic:

| Model config | Tasks | Attempts | Passes | Diagnostic pass rate | Gate decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `openai/gpt-5.5[medium]` | 36 | 36 | 25 | 69.4% | all tasks need more rollouts |

Primary ceiling by category/size:

| Category / size | Passes | Attempts |
| --- | ---: | ---: |
| artifact / small | 4 | 4 |
| artifact / medium | 1 | 4 |
| artifact / large | 0 | 4 |
| code / small | 4 | 4 |
| code / medium | 4 | 4 |
| code / large | 4 | 4 |
| workflow / small | 4 | 4 |
| workflow / medium | 2 | 4 |
| workflow / large | 2 | 4 |

Tasks that failed both ceiling rows:

- `access-log-to-incidents`
- `audit-log-normalization`
- `billing-revenue-rollup`
- `feature-branch-select-commits`
- `ledger-schema-upgrade`
- `markdown-table-inventory`
- `merge-divergent-config-branches`
- `release-branch-cherry-pick`
- `subscription-summary-report`
- `support-metrics-package`
- `ticket-update-dont-duplicate`

Failure triage from verifier output:

| Failure mode | Count |
| --- | ---: |
| missing required output file | 4 |
| artifact output mismatch | 4 |
| branch context failure | 1 |
| schema output mismatch | 1 |
| workflow state mismatch | 1 |

Decision:

Under the revised protocol, this run is useful ceiling-smoke evidence, not a final admission gate.
N=1 cannot accept or evict individual tasks under the pre-registered 75% one-shot ceiling gate. All
36 tasks need more ceiling rollouts before final admission. The 11 double-ceiling failures remain
the highest-priority audit targets because they are the best evidence of prompt/verifier ambiguity
or oversizing, but they are not automatic evictions.

Interpretation:

This result changes the calibration priority. The N=1 floor probe showed a useful cheap-model
gradient, and the ceiling smoke identifies where that gradient may be contaminated by ambiguity or
task oversizing. The artifact-large cell is the clearest audit target: cheap models failed it, and
both ceiling rows also failed all four tasks on first submit. Code tasks are the opposite: the
primary ceiling passed all code tasks, while the cheap floor probe suggests medium and large code
may still be too easy.

## 2026-07-04: first alternate-solution admission proofs

Purpose: start converting the candidate task set from locally valid tasks into snapshot-admissible
tasks by adding materially different alternate-solution evidence.

Tasks:

- `date-window-inclusive`
- `settings-null-default`
- `retry-error-fallback`
- `extract-error-fields`
- `strip-sort-allowlist`
- `env-flags-to-json`
- `invoice-cli-regression-test-fix`
- `move-module-fix-imports`
- `post-build-status`
- `rename-helper-symbol`
- `spec-to-release-checklist`
- `ticket-cut-from-bug-report`
- `auth-token-expiry-regression`
- `report-json-format`
- `split-notification-renderer`
- `user-export-field-rename`
- `config-flag-ignored`
- `dependency-api-rename`
- `release-branch-cherry-pick`
- `ticket-update-dont-duplicate`

Alternate solutions:

- Added `tasks/date-window-inclusive/solution_alt/solve.sh`.
- The reference solution rewrites `date_window/events.py`; the alternate solution performs a
  targeted comparator edit from exclusive end-date filtering to inclusive end-date filtering.
- Added `tasks/settings-null-default/solution_alt/solve.sh`.
- The reference solution rewrites `settings_app/config.py`; the alternate solution performs a
  targeted edit replacing brittle notification indexing with explicit defaults.
- Added `tasks/retry-error-fallback/solution_alt/solve.sh`.
- The reference solution rewrites `retry_parser/parser.py`; the alternate solution structures the
  fallback as constants plus a helper while preserving valid-row parsing.
- Added `tasks/extract-error-fields/solution_alt/solve.sh`.
- The reference solution writes an inline one-pass CSV transformer; the alternate solution defines
  explicit `FIELDS`, `flatten`, and `main` functions before generating output.
- Added `tasks/strip-sort-allowlist/solution_alt/solve.sh`.
- The reference solution uses a direct loop and set; the alternate solution uses a normalization
  helper and set comprehension.
- Added `tasks/env-flags-to-json/solution_alt/solve.sh`.
- The reference solution uses a compact parser; the alternate solution separates line parsing from
  value coercion.
- Added `tasks/invoice-cli-regression-test-fix/solution_alt/solve.sh`.
- The reference solution tests the importer directly; the alternate solution adds a CLI-level
  regression test and fixes duplicate handling with an insertion-ordered dictionary.
- Added `tasks/move-module-fix-imports/solution_alt/solve.sh`.
- The reference solution writes all destination files from literals; the alternate solution copies
  the existing helper source into the new module and updates imports/wrappers.
- Added `tasks/post-build-status/solution_alt/solve.sh`.
- The reference solution writes an inline script; the alternate solution separates status building
  from API-state writing.
- Added `tasks/rename-helper-symbol/solution_alt/solve.sh`.
- The reference solution rewrites package files; the alternate solution performs a targeted symbol
  replacement in the two affected files.
- Added `tasks/spec-to-release-checklist/solution_alt/solve.sh`.
- The reference solution uses a regex parser; the alternate solution parses bracket markers without
  regex.
- Added `tasks/ticket-cut-from-bug-report/solution_alt/solve.sh`.
- The reference solution uses inline branching; the alternate solution uses a rule table and
  classifier.
- Added medium code/workflow alternates for `auth-token-expiry-regression`, `report-json-format`,
  `split-notification-renderer`, `user-export-field-rename`, `config-flag-ignored`,
  `dependency-api-rename`, `release-branch-cherry-pick`, and `ticket-update-dont-duplicate`.
- These alternates use different implementation structures from their references: helper functions,
  renderer maps, copied source moves, dynamic patch/ticket selection, or module imports instead of
  direct literal rewrites.

Verification:

```text
tmp=$(mktemp -d /tmp/shallowswe-date-window-alt.XXXXXX)
cp -R tasks/date-window-inclusive/environment/. "$tmp/app"
APP_DIR="$tmp/app" bash tasks/date-window-inclusive/solution_alt/solve.sh
APP_DIR="$tmp/app" LOG_DIR="$tmp/logs" bash tasks/date-window-inclusive/tests/test.sh
cat "$tmp/logs/reward.txt"

tmp=$(mktemp -d /tmp/shallowswe-settings-alt.XXXXXX)
cp -R tasks/settings-null-default/environment/. "$tmp/app"
APP_DIR="$tmp/app" bash tasks/settings-null-default/solution_alt/solve.sh
APP_DIR="$tmp/app" LOG_DIR="$tmp/logs" bash tasks/settings-null-default/tests/test.sh
cat "$tmp/logs/reward.txt"

for t in retry-error-fallback extract-error-fields strip-sort-allowlist env-flags-to-json; do
  tmp=$(mktemp -d "/tmp/shallowswe-${t}-alt.XXXXXX")
  cp -R "tasks/$t/environment/." "$tmp/app"
  APP_DIR="$tmp/app" bash "tasks/$t/solution_alt/solve.sh"
  APP_DIR="$tmp/app" LOG_DIR="$tmp/logs" bash "tasks/$t/tests/test.sh"
  cat "$tmp/logs/reward.txt"
done

for t in invoice-cli-regression-test-fix move-module-fix-imports post-build-status \
  rename-helper-symbol spec-to-release-checklist ticket-cut-from-bug-report; do
  tmp=$(mktemp -d "/tmp/shallowswe-${t}-alt.XXXXXX")
  cp -R "tasks/$t/environment/." "$tmp/app"
  APP_DIR="$tmp/app" bash "tasks/$t/solution_alt/solve.sh"
  APP_DIR="$tmp/app" LOG_DIR="$tmp/logs" bash "tasks/$t/tests/test.sh"
  cat "$tmp/logs/reward.txt"
done

for t in auth-token-expiry-regression split-notification-renderer user-export-field-rename \
  dependency-api-rename release-branch-cherry-pick ticket-update-dont-duplicate; do
  tmp=$(mktemp -d "/tmp/shallowswe-${t}-alt.XXXXXX")
  cp -R "tasks/$t/environment/." "$tmp/app"
  APP_DIR="$tmp/app" bash "tasks/$t/solution_alt/solve.sh"
  APP_DIR="$tmp/app" LOG_DIR="$tmp/logs" bash "tasks/$t/tests/test.sh"
  cat "$tmp/logs/reward.txt"
done

for t in report-json-format config-flag-ignored; do
  tmp=$(mktemp -d "/tmp/shallowswe-${t}-alt.XXXXXX")
  cp -R "tasks/$t/environment/." "$tmp/app"
  APP_DIR="$tmp/app" bash "tasks/$t/solution_alt/solve.sh"
  docker run --rm -e PYTHONPATH=/app \
    -v "$tmp/app:/app" -v "$tmp/logs:/logs" \
    -v "$PWD/tasks/$t/tests/test.sh:/test.sh:ro" \
    python:3.12-slim bash /test.sh
  cat "$tmp/logs/verifier/reward.txt"
done
```

Results:

```text
1
1
1
1
1
1
1
1
1
1
1
1
1
1
1
1
1
1
1
1
```

Updated admission artifact:

```text
results/shallowswe-admission-audit-2026-07-04/admission-audit.json
```

## 2026-07-04: v2 complete alternate-solution admission proof

Purpose: close the remaining task-local snapshot admission blocker by validating at least one
materially different alternate solution for every official task.

Added alternate solutions for the remaining 16 official tasks:

- Artifact tasks: `access-log-to-incidents`, `markdown-table-inventory`,
  `subscription-summary-report`, `audit-log-normalization`, `billing-revenue-rollup`,
  `support-metrics-package`, `payout-reconcile`, and `ledger-schema-upgrade`.
- Large code/workflow tasks: `api-pagination-consistency`,
  `cache-invalidates-on-settings-change`, `webhook-idempotency-parity`, `config-key-rollover`,
  `feature-branch-select-commits`, `merge-divergent-config-branches`,
  `status-terminal-parity`, and `ticket-state-reconcile`.

Alternate-solution independence:

- Script-rerun artifact tasks use general parsers and aggregators that run on verifier-created
  hidden inputs, not visible-output constants.
- Package patch tasks replace the relevant runtime modules while preserving existing CLI/module
  surfaces.
- Workflow tasks produce the required final repo/API state through independent file-generation or
  reconciliation logic rather than copying the reference patch structure.

Verification commands:

```text
for t in access-log-to-incidents markdown-table-inventory subscription-summary-report \
  audit-log-normalization billing-revenue-rollup support-metrics-package; do
  tmp=$(mktemp -d)
  mkdir -p "$tmp/app" "$tmp/logs"
  cp -R "tasks/$t/environment/." "$tmp/app/"
  APP_DIR="$tmp/app" bash "tasks/$t/solution_alt/solve.sh"
  APP_DIR="$tmp/app" LOG_DIR="$tmp/logs" bash "tasks/$t/tests/test.sh"
  cat "$tmp/logs/reward.txt"
done

for t in payout-reconcile ledger-schema-upgrade config-key-rollover \
  status-terminal-parity ticket-state-reconcile; do
  tmp=$(mktemp -d)
  mkdir -p "$tmp/app" "$tmp/logs"
  cp -R "tasks/$t/environment/." "$tmp/app/"
  docker run --rm -v "$tmp/app:/app" \
    -v "$PWD/tasks/$t/solution_alt/solve.sh:/solve.sh:ro" \
    python:3.12-slim bash /solve.sh
  docker run --rm -e PYTHONPATH=/app \
    -v "$tmp/app:/app" -v "$tmp/logs:/logs/verifier" \
    -v "$PWD/tasks/$t/tests/test.sh:/test.sh:ro" \
    python:3.12-slim bash /test.sh
  cat "$tmp/logs/reward.txt"
done

for t in api-pagination-consistency cache-invalidates-on-settings-change \
  webhook-idempotency-parity feature-branch-select-commits \
  merge-divergent-config-branches; do
  tmp=$(mktemp -d)
  mkdir -p "$tmp/app" "$tmp/logs"
  cp -R "tasks/$t/environment/." "$tmp/app/"
  APP_DIR="$tmp/app" bash "tasks/$t/solution_alt/solve.sh"
  APP_DIR="$tmp/app" LOG_DIR="$tmp/logs" bash "tasks/$t/tests/test.sh"
  cat "$tmp/logs/reward.txt"
done

uv run python -m unittest discover -s tests
uv run ruff check src tests
uv run shallowswe tasks tasks
uv run shallowswe admission-audit tasks
```

Results:

```text
All 16 newly added alternate solutions returned reward=1.
Unit tests: 56 passed.
Ruff: all checks passed.
Task metadata validation: 37 tasks validated.
Admission audit:
  official_task_count=36
  ready_task_count=36
  ready_for_snapshot=true
  issue_counts={}
```

Updated admission artifact:

```text
results/shallowswe-admission-audit-2026-07-04/admission-audit.json
```

## 2026-07-04: v2 calibration budget readiness

Purpose: verify the snapshot-ready local task set against calibration manifests and produce budget
evidence before paid high-N one-shot runs.

Protocol alignment fixes:

- `panels/shallowswe-ceiling-v0.1.json` now states the v2 one-shot ceiling gate:
  `12/16` accepts, `11/16` investigates, and `<=10/16` fixes or evicts.
- The ceiling panel now separates the primary admission row from the optional independent audit
  row. The audit row is a fresh diagnostic run only; it is never a fallback, cascade, scored
  substitute, or continuation of the primary row.
- `panels/shallowswe-calibration-v0.1.json` now states the v2 floor bands:
  small `70-100%`, medium `30-70%`, large `0-40%`.
- `src/shallowswe/calibration.py` now uses the v2 large-band floor count, `0-40%`, when ranking
  floor candidates.

Budget artifact:

```text
results/shallowswe-calibration-budget-2026-07-04/budget-estimates.json
```

Conservative estimates use this token basis:

```text
input_tokens=150000
output_tokens=8000
cache_read_tokens=100000
cache_write_tokens=0
```

| Run | Attempts | Conservative estimate | Budget guard | Status |
| --- | ---: | ---: | ---: | --- |
| Primary ceiling, N=16, 36 tasks | 576 | `$311.04` | `$200` | over guard |
| Ceiling panel if both rows were run everywhere, not protocol default | 1152 | `$599.04` | `$200` | over guard |
| Floor candidate panel, N=10, 36 tasks | 1080 | `$118.98` | `$500` | under guard |

Observed N=1 ceiling smoke diagnostics:

| Row | Attempts | Average price-sheet cost/attempt | Projected primary N=16 |
| --- | ---: | ---: | ---: |
| `openai/gpt-5.5[medium]` | 36 | `$0.20033` | `$115.39` |

Decision:

- Do not run both ceiling rows across all tasks. Admission is primary-row only; the audit row is
  reserved for independent task-QA diagnosis of primary-ceiling failures.
- Do not launch the paid primary-ceiling N=16 run under the current `$200` conservative guard. The
  observed smoke projection is useful, but it is diagnostic rather than the spend guard.
- The floor-candidate N=10 sweep is within the conservative `$500` guard and is ready to run once
  spend is explicitly accepted.

Environment readiness:

```text
/Users/lydakis/Developer/blue/apps/supervisor/.env.local exists
OPENROUTER_API_KEY is present in that env file
```

Validation:

```text
uv run python -m unittest tests.test_calibration_protocol tests.test_calibration tests.test_budget
uv run python -m unittest discover -s tests
uv run ruff check src tests
uv run python -m json.tool panels/shallowswe-ceiling-v0.1.json
uv run python -m json.tool results/shallowswe-calibration-budget-2026-07-04/budget-estimates.json
uv run shallowswe admission-audit tasks
```

Results:

```text
Focused protocol/calibration/budget tests: 21 passed.
Full unit test suite: 57 passed.
Ruff: all checks passed.
JSON artifacts parse successfully.
official_task_count=36
ready_task_count=36
ready_for_snapshot=true
issue_counts={}
```

Admission status after this proof:

| Official tasks | Ready local tasks | Remaining local blocker |
| ---: | ---: | --- |
| 36 | 36 | none locally; paid one-shot calibration still pending |

## 2026-07-04: v2 task metadata floor-evidence sync

Purpose: make task-local metadata match the measured selected-floor evidence instead of carrying
placeholder pass-rate fields.

Evidence artifact:

```text
results/shallowswe-floor-probe-n1-v2-postfix-2026-07-04/task-floor-evidence.json
```

Source rollouts:

```text
results/shallowswe-floor-probe-n1-v2-postfix-2026-07-04/rollouts.json
```

Update:

- Selected floor row: `google/gemini-3.5-flash`.
- Official task metadata now records `weakest_model_rollouts = 1` for all 36 official tasks.
- `weakest_model_pass_rate` now records the selected-floor N=1 one-shot result for each task.
- All official tasks are marked `calibration_status = "candidate"` because high-N one-shot ceiling
  and floor calibration are still pending.

Measured selected-floor N=1 shape:

```text
official_task_count=36
status_counts={"candidate": 36}
selected_floor_passes=24
selected_floor_failures=12
```

Category/size pass rates:

| Category / size | Pass rate |
| --- | ---: |
| artifact / small | 1.000 |
| artifact / medium | 0.250 |
| artifact / large | 0.250 |
| code / small | 1.000 |
| code / medium | 1.000 |
| code / large | 0.750 |
| workflow / small | 1.000 |
| workflow / medium | 0.500 |
| workflow / large | 0.250 |

Validation:

```text
uv run python -m unittest tests.test_calibration_protocol tests.test_v1_task_matrix \
  tests.test_task_metadata tests.test_admission
uv run shallowswe tasks tasks
uv run shallowswe admission-audit tasks
```

Results:

```text
16 tests passed.
Task metadata validation: 37 tasks validated.
Admission audit:
  official_task_count=36
  ready_task_count=36
  ready_for_snapshot=true
  issue_counts={}
```

## 2026-07-04: v2 protocol-freeze wording pass

Purpose: make the scoring protocol impossible to misread as fallback, escalation, ensembling, or
runtime model dispatch.

Spec changes:

- Added a named single-model run invariant: every scored row is bound to one `model_config`
  `(model, effort, sampling_config)` for all agent turns, verifier-feedback continuations, and cap
  outcomes.
- Renamed the public hero from routing language to the single-model reliability-cost frontier.
- Replaced "route this work" language with up-front single-model selection language.
- Added the suite-level weighted CPSC formula:
  `sum_t weight_t * mean_spend(m,t) / sum_t weight_t * solve_rate(m,t)`.
- Fixed the v1 single-model eligibility floor at 90% scored repair-loop solve rate.
- Predeclared rollout counts: plumbing `N=1`, ceiling admission `N=16`, floor calibration `N=10`,
  published scoring `N=10`, and report-grade disputed cells `N=20`.
- Added hero tie behavior for overlapping CPSC intervals and "no recommended configuration" slices.
- Split context exhaustion into scored model failures after meaningful progress vs excluded
  packaging/dispatch/scaffold failures before meaningful work begins.
- Renamed excluded infra failure wording from routing failures to model-resolution and
  provider-dispatch failures.
- Added transcript redaction policy that cannot remove model outputs, commands, code edits,
  verifier submissions, or agent-facing verifier feedback.
- Inserted a protocol-freeze step before suite authoring in the build order.

Validation:

```text
uv run python -m unittest tests.test_calibration_protocol
rg -n "routing" SPEC.md docs/methodology.md docs/calibration-protocol.md \
  docs/pier-integration.md docs/task-selection-rubric.md docs/task-sourcing-methodology.md \
  docs/verifier-contract.md README.md docs/pilot-plan.md
```

Results:

```text
12 tests passed.
No remaining "routing" wording in the active public spec/methodology docs checked above.
```

## 2026-07-04: v2 post-feedback validation

Validation commands:

```text
uv run python -m unittest discover -s tests
uv run ruff check src tests
uv run shallowswe tasks tasks
uv run shallowswe admission-audit tasks
uv run python -m json.tool \
  results/shallowswe-floor-probe-n1-v2-postfix-2026-07-04/task-floor-evidence.json
uv run python -m json.tool results/shallowswe-admission-audit-2026-07-04/admission-audit.json
uv run python -m json.tool \
  results/shallowswe-calibration-budget-2026-07-04/budget-estimates.json
```

Results:

```text
Full unit test suite: 59 passed.
Ruff: all checks passed.
Task metadata validation: 37 tasks validated.
Admission audit:
  official_task_count=36
  ready_task_count=36
  ready_for_snapshot=true
  issue_counts={}
JSON artifacts parse successfully.
```

## 2026-07-04: v2 pre-registered calibration plan

Purpose: make the remaining high-N calibration work executable and auditable without starting a
paid run.

Added:

- `configs/shallowswe-v1-calibration-plan.json`, a machine-readable plan for the pending v1
  calibration runs.
- `shallowswe calibration-plan`, a CLI audit that validates the plan against the current task set,
  panel manifests, budget estimates, per-task calibration metadata, and no-fallback panel settings.
- `results/shallowswe-calibration-plan-2026-07-04/plan-audit.json`, the saved audit output for
  the current checkout.

Plan groups:

```text
ceiling-admission-primary-n16:
  mode=one_shot
  row_ids=ceiling_gpt_5_5_medium
  target_rollouts_per_task=16
  planned_attempts=576
  budget_status=approval_required
  conservative_estimated_full_panel_cost_usd=311.04
  budget_limit_usd=200

floor-size-calibration-panel-n10:
  mode=one_shot
  row_ids=anchor_gemini_3_5_flash_medium,
          anchor_glm_5_2_high,
          anchor_kimi_k2_7_code_default
  target_rollouts_per_task=10
  planned_attempts=1080
  budget_status=within_budget
  conservative_estimated_full_panel_cost_usd=118.98
  budget_limit_usd=500
```

Current audit result:

```text
schema_version=shallowswe.calibration_plan_audit.v0.1
official_task_count=36
planned_official_task_count=36
valid=true
ready_to_run_without_budget_override=false
issues=[]
run_group_issue_counts={}
budget_status_counts={
  approval_required: 1,
  within_budget: 1
}
```

Validation:

```text
uv run python -m unittest discover -s tests
uv run ruff check src tests
uv run shallowswe tasks tasks
uv run shallowswe admission-audit tasks
uv run python -m unittest tests.test_calibration_plan tests.test_cli \
  tests.test_calibration_protocol
uv run ruff check src/shallowswe/calibration_plan.py src/shallowswe/cli.py \
  tests/test_calibration_plan.py
uv run shallowswe calibration-plan configs/shallowswe-v1-calibration-plan.json
```

Results:

```text
Full unit test suite: 63 passed.
Ruff: all checks passed.
Task metadata validation: 37 tasks validated.
Admission audit remains locally ready and calibrated-snapshot pending:
  ready_for_snapshot=true
  ready_for_calibrated_snapshot=false
19 focused tests passed.
Ruff focused check passed.
Calibration plan audit passed and correctly requires explicit approval for the conservative
ceiling-primary N=16 budget.
```

## 2026-07-04: v2 structured calibration provenance

Purpose: prevent local admission readiness from being mistaken for a fully calibrated snapshot.

Task metadata update:

- Added `[calibration]`, `[calibration.ceiling]`, and `[calibration.floor]` provenance sections to
  all 36 official task manifests.
- Recorded the candidate snapshot id `shallowswe-v0.1-candidate-2026-07-04`.
- Recorded current N=1 ceiling-smoke pass counts from
  `results/shallowswe-ceiling-smoke-gpt55-medium-n1-2026-07-04/rollouts.json`.
- Recorded current N=1 selected-floor pass counts from
  `results/shallowswe-floor-probe-n1-v2-postfix-2026-07-04/rollouts.json`.
- Recorded target counts: ceiling admission `N=16`, floor calibration `N=10`.
- Set `admission_decision = "candidate_pending_high_n"` and
  `size_assignment_decision = "candidate_pending_high_n_floor"` for every official task.

Audit schema update:

- `shallowswe admission-audit` now emits `schema_version = "shallowswe.admission_audit.v0.2"`.
- `ready_for_snapshot` remains the local package/admission readiness flag.
- `ready_for_calibrated_snapshot` is the stricter final snapshot flag and remains false until
  accepted calibration decisions and target rollout counts exist.

Current audit result:

```text
official_task_count=36
ready_task_count=36
ready_for_snapshot=true
ready_for_calibrated_snapshot_count=0
ready_for_calibrated_snapshot=false
issue_counts={}
calibration_issue_counts={
  admission_decision_not_accepted: 36,
  pending_ceiling_rollouts: 36,
  pending_floor_rollouts: 36,
  size_assignment_not_accepted: 36
}
```

Validation:

```text
uv run python -m unittest tests.test_admission tests.test_calibration_protocol tests.test_cli
uv run ruff check src/shallowswe/admission.py tests/test_admission.py \
  tests/test_calibration_protocol.py
uv run shallowswe admission-audit tasks
```

Results:

```text
20 focused tests passed.
Ruff focused check passed.
Admission audit regenerated at:
  results/shallowswe-admission-audit-2026-07-04/admission-audit.json
```

## 2026-07-04: v2 post-feedback full validation

Purpose: verify the final spec wording and calibration-provenance updates after clarifying that
ShallowSWE uses one model configuration per scored run and no fallback/cascade behavior.

Validation:

```text
uv run python -m unittest discover -s tests
uv run ruff check src tests
uv run shallowswe tasks tasks
uv run shallowswe admission-audit tasks
uv run python -m json.tool results/shallowswe-admission-audit-2026-07-04/admission-audit.json
uv run python -m json.tool \
  results/shallowswe-floor-probe-n1-v2-postfix-2026-07-04/task-floor-evidence.json
uv run python -m json.tool \
  results/shallowswe-calibration-budget-2026-07-04/budget-estimates.json
```

Results:

```text
Full unit test suite: 61 passed.
Ruff: all checks passed.
Task metadata validation: 37 tasks validated.
Admission audit:
  schema_version=shallowswe.admission_audit.v0.2
  official_task_count=36
  ready_task_count=36
  ready_for_snapshot=true
  ready_for_calibrated_snapshot_count=0
  ready_for_calibrated_snapshot=false
  issue_counts={}
  calibration_issue_counts={
    admission_decision_not_accepted: 36,
    pending_ceiling_rollouts: 36,
    pending_floor_rollouts: 36,
    size_assignment_not_accepted: 36
  }
JSON artifacts parse successfully.
```

## 2026-07-04: v0.1 candidate-suite completion decision

Purpose: record the current stopping point after deciding not to spend on high-N calibration before
the first repair-loop pilot.

Decision:

- The 36 official tasks are complete as the ShallowSWE v0.1 candidate suite.
- Current evidence is sufficient for local task quality and cheap calibration signal:
  reference packaging passes, base fixtures fail, alternate solutions exist, task metadata validates,
  and the selected floor N=1 probe has useful failure spread.
- The high-N one-shot ceiling and floor runs are deferred. They are required for a public
  statistically calibrated snapshot, not for calling the authored 36-task candidate suite done.
- The next useful empirical step is a bounded repair-loop pilot on a small subset, because final
  ShallowSWE CPSC is measured from repair loops, not high-N one-shot calibration.

Current machine-readable status:

```text
admission-audit:
  official_task_count=36
  ready_task_count=36
  ready_for_snapshot=true
  ready_for_calibrated_snapshot=false

calibration-plan:
  valid=true
  ready_to_run_without_budget_override=false
  budget_status_counts={
    approval_required: 1,
    within_budget: 1
  }
```

Interpretation:

`ready_for_snapshot=true` means the task packets are locally ready and the v0.1 candidate suite can
be treated as complete. `ready_for_calibrated_snapshot=false` remains intentional: it protects the
stronger public claim until high-N ceiling/floor calibration is actually run or explicitly replaced
by a cheaper pre-registered public-admission policy.

## 2026-07-04: repair-loop pilot capability gate

Purpose: prepare the first bounded repair-loop pilot without spending on a run that cannot satisfy
the final protocol.

Pilot subset:

| Task | Category | Size | Current floor signal |
| --- | --- | --- | ---: |
| `invoice-cli-regression-test-fix` | code | small | 1.0 |
| `cache-invalidates-on-settings-change` | code | large | 0.0 |
| `env-flags-to-json` | artifact | small | 1.0 |
| `access-log-to-incidents` | artifact | medium | 0.0 |
| `config-flag-ignored` | workflow | medium | 1.0 |
| `merge-divergent-config-branches` | workflow | large | 0.0 |

Decision:

- The pilot subset is a good cheap protocol exerciser: it covers all three categories, all three
  sizes, and both easy and failure-prone floor signals.
- Stock Pier plus stock `mini-swe-agent` is not final-protocol eligible. It can run one-shot
  calibration, and a custom wrapper could preserve filesystem state, but stock mini-swe does not
  resume the same model conversation across hidden-verifier submissions.
- A filesystem-only loop remains allowed only as a plumbing smoke. It must not be reported as
  repair-loop CPSC.
- The local `lydakis/mini-swe-agent` fork plus
  `shallowswe.pier_agents.resumable_mini_swe_agent:ResumableMiniSweAgent` satisfies the
  conversation-continuation gate for the pilot.

Current machine-readable status:

```text
repair-loop-pilot-plan:
  valid=true
  ready_for_final_protocol_pilot=true
  can_run_protocol_smoke=true
  final_protocol_eligible_model_configs=[
    resumable_mini_swe_gemini_3_5_flash_medium
  ]
  blockers=[]
```

## 2026-07-04: bounded repair-loop pilot, three-row smoke

Purpose: validate the final bounded repair-loop protocol end to end without starting a broad
benchmark run.

Run shape:

```text
tasks:
  - env-flags-to-json
  - cache-invalidates-on-settings-change
  - config-flag-ignored
model_config: openrouter/google/gemini-3.5-flash
agent: shallowswe-resumable-mini-swe-agent
mini-swe source: /Users/lydakis/Developer/oss/mini-swe-agent
max verifier submissions: 3 for env-flags-to-json, 2 for the other rows
artifacts:
  results/shallowswe-repair-loop-pilot-2026-07-04/repair-loop-results.json
  results/shallowswe-repair-loop-pilot-2026-07-04/repair-loop-aggregate-priced.json
  results/shallowswe-repair-loop-pilot-2026-07-04/repair-loop-aggregate-model.json
```

Results:

| Task | Category | Size | Passed | Verifier submissions | Agent steps | Price-sheet spend |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `env-flags-to-json` | artifact | small | yes | 1 | 17 | `$0.17139825` |
| `cache-invalidates-on-settings-change` | code | large | yes | 2 | 19 | `$0.12958110` |
| `config-flag-ignored` | workflow | medium | yes | 1 | 18 | `$0.07788825` |

Model-level aggregate:

```text
repair_loops=3
successes=3
solve_rate=1.0
mean_verifier_submissions_to_success=1.3333333333333333
total_model_spend_usd=0.3788676
cpsc=0.12628920000000002
```

Protocol notes:

- The small artifact row validated the first-submit success path.
- The workflow row covers the third public category and also passed on the first verifier
  submission.
- The code-large row validated the repair path: first trajectory submitted and failed hidden
  verification; the second trajectory contains exactly one sanitized feedback message,
  `Verification failed. Continue working.`, and then passed.
- During development, an earlier strictness bug was found: the controller originally ran the hidden
  verifier after a mini-swe `LimitsExceeded` exit. The controller now only verifies after
  `exit_status=Submitted`; a cap exit stops the row as a cap failure.

Decision:

The bounded repair-loop protocol is validated end to end for a small paid pilot. This is not a
statistical benchmark result and should not be presented as a leaderboard claim.

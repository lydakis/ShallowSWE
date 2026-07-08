# Medium/Large Refill Candidate Cards

Status: draft for review. Written 2026-07-05, while the post-amendment floor recalibration
(`configs/shallowswe-floor-recal-oneshot-n3.json`) is in flight.

## Why this file exists

The 2026-07-05 spec amendments removed the last spec-ambiguity difficulty from the frozen 18-task
suite. The clean preview run (195/195 solved, all 10 panel configs) and the pending floor
recalibration are expected to confirm that every current task sits in the small band. That vacates
the medium and large cells of the 3x3 category/size matrix.

This file now tracks the active 20-entry candidate funnel. Difficulty must come from engineering
surface, never from spec tightness. Every candidate keeps the formal ceiling invariant: an Extra
High frontier model should one-shot it by reading the repo, while the floor should still thrash on
one named lever.

## Design rules (carried over, plus lessons from 2026-07-05)

- Full output contracts in the instruction. If the verifier asserts it, the instruction or the
  visible repo derives it. No guessing games; we measured what those cost.
- Verifiers run on fresh seeded roots (stateless), assert structurally where prose is not the
  contract, and rerun on hidden inputs to catch hardcoding.
- Two materially different correct solutions must pass before admission.
- Two-sided gate, pre-registered per card: formal ceiling one-shot >= 75% on
  `openai/gpt-5.5[extra_high]`; floor one-shot inside the target band (medium 30-70%,
  large 0-40%) measured on `panels/shallowswe-calibration-v0.1.json`.
- Demotion rule: if the floor saturates a candidate at N>=10, it is relabeled small or reshaped.
  It is not kept as a special tier.
- Fixture repos grow to 30-80 files for large candidates. Navigation and state are the difficulty;
  no algorithmic cleverness, no deep architecture.

## Named difficulty levers

- **L1 repo-scale navigation** — the change is easy; finding all the places it applies is not.
- **L2 cross-file invariants** — local patches break neighboring behavior the verifier re-checks.
- **L3 parity-except-bug** — preserve existing behavior byte-for-byte except one specified fix.
- **L4 constraint conjunction** — every requirement is trivial; eight of them must hold at once.
- **L5 reconcile-don't-duplicate at volume** — idempotent updates against partial prior state.
- **L6 sequencing** — step order matters; a wrong early step must be detected and unwound.
- **L7 edge-case compounding** — boundaries (time zones, rounding, ordering) interact.

## Candidate set

| Slot | Candidate ID | Category | Size | Primary lever |
| --- | --- | --- | --- | --- |
| CM-1 | `retry-policy-migration` | code | medium | L2 |
| CM-2 | `notification-locale-fallback` | code | medium | L3 |
| CL-1 | `dispatch-planner-split-parity` | code | large | L3 + L1 |
| CL-2 | `invoice-multi-source-merge` | code | large | L4 |
| AM-1 | `access-log-sessionize` | artifact | medium | L7 |
| AM-2 | `billing-proration-schedule` | artifact | medium | L4 |
| AL-1 | `privacy-retention-evidence-package` | artifact | large | L7 + L5 + L4 |
| AL-2 | `repo-observability-coverage-audit` | artifact | large | L7 + L5 + L4 |
| WM-1 | `ticket-bulk-triage` | workflow | medium | L5 |
| WL-5 | `status-fanout-reconcile` | workflow | large | L5 + L6 + L4 |
| WM-3 | `ticket-update-dont-duplicate` | workflow | medium | L5 |
| WL-1 | `release-train-reconcile` | workflow | large | L6 + L5 |
| WL-2 | `tenant-offboarding-reconcile` | workflow | large | L5 + L6 |
| WL-3 | `config-key-rollover` | workflow | large | L2 + L3 |
| CL-3 | `seat-compliance-admin-console` | code | large | L1 + L2 + L4 |
| CL-4 | `feature-entitlements-admin-screen` | code | large | L1 + L4 |
| CL-5 | `renewal-risk-admin-screen` | code | large | L1 + L4 |
| CL-6 | `customer-health-dashboard-screen` | code | large | L1 + L2 + L4 |
| AL-4 | `vendor-risk-evidence-package` | artifact | large | L7 + L5 + L4 |
| WL-4 | `incident-comms-pipeline` | workflow | large | L5 + L6 + L4 |

Current branch status: all 20 tranche-1 funnel entries are authored tasks or repair candidates and
are intentionally excluded from frozen benchmark counts until they pass the admission and
calibration gates.

2026-07-07 Codex subscription tranche result:

- Current active funnel audit: 20 authored candidates, 12 provisional `keep_large` tasks, and 8
  `too_easy_duplicate` tasks after trajectory review and replacement.
- New medium probes: 6 tasks, medium smoke `gpt-5.5[medium]` 6/6, floor
  `gpt-5.4-mini[low]` 16/18. This is not formal ceiling evidence; formal admission still requires
  `gpt-5.5[extra_high]`.
- Corrected large-heavy probe: 11 tasks, formal Extra High probe `gpt-5.5[extra_high]` 9/11,
  floor `gpt-5.4-mini[low]` 3/11. This was an N=1 admission screen, not the full N=8 gate.
- Repaired config/incident probe:
  `results/shallowswe-codex-subscription-sizing-2026-07-07-v1-repaired-config-incident-packaged-xhigh-n1`.
  This used `gpt-5.5[extra_high]` as the formal ceiling and treated any medium rows as smoke-only.
  `config-key-rollover` passed Extra High but also passed the low floor, so it is too easy for the
  large tranche after repair. `incident-comms-pipeline` now has visible replay/API-call-log coverage;
  the repaired low floor failed fairly, the first repaired Extra High attempt timed out at 900s,
  and the 1200s Extra High retry passed visible and hidden verification with a clean trajectory
  audit. It is now the active WL-4 provisional workflow-large keep.
- `retry-policy-migration`, `notification-locale-fallback`, `access-log-sessionize`,
  `billing-proration-schedule`, and `ticket-bulk-triage` each saturated the floor at 3/3 after
  trajectory audit. Treat them as too easy for medium; reshape or archive.
- `status-fanout-reconcile` was expanded from the smaller WM-2 medium candidate into WL-5 with
  status, gate, notification, call-log, and summary reconciliation. The repaired low floor failed
  fairly, and the Extra High probe passed validly, so it is now a provisional workflow-large keep.
- Earlier large probes CL-1, the original AL-1 `ledger-restatement-audit`, and the original AL-2
  `support-sla-business-hours` were too
  easy for their large hypotheses and should be reshaped or archived rather than carried forward as
  large tasks. `ledger-restatement-audit` was expanded again with account/entity/currency
  ownership, period close state, approvals, account/period moves, owner impact, and broader audit
  outputs; the low floor still passed validly, so it remains too easy for artifact-large and Extra
  High was not run.
- AL-1 has been replaced in the active funnel by `privacy-retention-evidence-package`, a synthetic
  multi-service privacy retention evidence package. Its low floor failed fairly on a documented
  action-label contract, and Extra High passed 1/1 validly with no trajectory gaming signal, so it
  is now a provisional artifact-large keep pending the full Extra High gate.
- `audit-log-normalization` was reshaped and rerun with the corrected Extra High ceiling policy.
  Extra High passed 1/1, but the verifier-repaired low floor also passed 1/1 with a generalized
  parser, so AL-5 is too easy for the large lane as written.
- Expanded `deployment-approval-reconcile` was tried as a WL-4 replacement. The new workflow
  contract adds change-request gates, owner notifications, idempotent notification replay, and a
  summary report. Reference solution replay passed, but the low floor also passed 1/1 with a
  generalized implementation, so it is too easy for the large lane as written. The active WL-4
  replacement is now `incident-comms-pipeline`.
- `renewal-risk-admin-screen` was expanded with engagement records, segment policies, renewal plan
  items, and a third owner-queue route. The low floor failed 0/1 fairly on owner escalation
  aggregation, then a bridge low-floor attempt failed fairly on risk-reason semantics after visible
  tests passed. Extra High passed 1/1 with hidden fixture success, so CL-5 is kept as a provisional
  large candidate. It still needs the full Extra High gate and a materially independent alternate
  solution before official admission.
- `invoice-multi-source-merge` now has two current low-floor failures after a valid Extra High
  probe. The bridge failure was a legitimate reject-ordering miss after the agent implemented all
  sources and a CSV-only regression test, so CL-2 is kept as a provisional large candidate pending
  the full Extra High gate.
- `customer-health-dashboard-screen` first expanded into a three-route command center with
  contracts, engagements, playbooks, an action queue, and an owner queue. That version saturated
  low floor after a metric-label verifier repair, so it was not accepted as large. It has now been
  expanded again with a recovery-plan route and JSON export and is tracked as CL-6. After an export
  projection verifier repair, low floor failed fairly and Extra High passed 1/1, so CL-6 is kept as
  provisional code-large pending the full Extra High gate. CL-3 has been filled by
  `seat-compliance-admin-console`, a four-route app feature for SaaS seat compliance with JSON
  export. After verifier/prompt repairs, the low floor failed fairly on row identity semantics and
  Extra High passed 1/1 with a generalized hidden-fixture solution, so CL-3 is kept as a
  provisional code-large candidate pending the full Extra High gate and independent alternate
  solution.
- `feature-entitlements-admin-screen` now has two current low-floor failures after a valid Extra
  High probe. The bridge failure was a legitimate multi-condition reason-code miss after the agent
  implemented both screens and passed its own visible tests, so CL-4 is kept as a provisional large
  candidate pending the full Extra High gate.
- `release-train-reconcile` was expanded with release manifests and promotion-ring readiness
  records. The post-expansion low floor failed fairly on phase ordering: it ran promotion checks
  after `update_changelog` even though all `run_check` rows must precede changelog work. The first
  Extra High failure exposed one prompt ambiguity around audit `detail` type, so the prompt was
  clarified. The corrected Extra High probe passed 1/1 with a plan-driven implementation and
  hidden-fixture success, so WL-1 is kept as a provisional workflow-large candidate pending the
  full Extra High gate.
- `incident-comms-pipeline` is now the active WL-4 provisional workflow-large keep after the 1200s
  Extra High retry passed visible and hidden verification. The prior 900s timeout is retained as
  historical evidence that this task is near the ceiling-time boundary, not as the current
  disposition. WL-2 has been replaced by `tenant-offboarding-reconcile`, an idempotent multi-state
  offboarding workflow.
  Its first Extra High attempt exposed an unfair verifier assumption about JSON list ordering, so
  the prompt/verifier were repaired to canonicalize non-semantic lists while preserving call-log
  sequence checks. After repair, the expanded low floor failed fairly and the repaired Extra High
  probe passed with a generalized hidden-fixture solution, so WL-2 is kept as a provisional
  workflow-large candidate pending the full Extra High gate.
- `billing-revenue-rollup` was expanded twice: first into a revenue close package, then into a
  contract/cash close package with `cash_application.csv`, `contract_variance.csv`, and
  `close_audit.json` cross-output controls. The latest low floor still passed 1/1 with a
  generalized visible/hidden solution, so AL-3 remains too easy for the large lane and should be
  replaced or materially reshaped rather than retried. AL-3 has been replaced in the active funnel
  by `developer-portal-api-index`, a non-tabular repository documentation/API inventory package.
  Its first low-floor run exposed an underspecified redirect `service_id` rule, which was repaired;
  after repair the low floor passed 1/1 with a generalized hidden-fixture solution, so that
  replacement was also too easy. AL-3 has now been replaced again by
  `sdk-migration-readiness-package`, a broader repository governance evidence package. Two
  prompt gaps were repaired (`actions` for ready rows and distinct wave counting); after repair,
  low floor passed 1/1 with a generalized hidden-fixture solution. This version is still too easy
  for the large lane as written. The active artifact replacement is now the expanded
  `repo-observability-coverage-audit`, a synthetic multi-service observability audit package. Its
  first route-scoped version was also too easy after verifier repair, but the remediation expansion
  added downstream trace edges, runbook freshness, rollback readiness, expanded rollups, and
  `remediation_plan.csv`. After one prompt repair and one verifier-whitespace repair, the repaired
  low floor failed fairly on board action priority and Extra High passed 1/1 with a generalized
  implementation, so AL-2 is kept as a provisional artifact-large candidate pending the full Extra
  High gate.
- `ledger-schema-upgrade` was expanded into a v4 ledger evidence package with temporal overrides,
  v1/v2/v3 usage formats, discounts, FX, credits, adjustments, balances, plan revenue, rejects, and
  audit metadata. The first floor failure found one underspecified audit total, so the contract was
  clarified. The corrected low floor passed 1/1 with a generalized hidden-fixture solution, so
  AL-4 remains too easy for the large lane after repair.
- AL-4 has been replaced in the active funnel by `vendor-risk-evidence-package`, a repository-scale
  vendor-risk evidence package. Its low floor failed fairly on source-evidence text semantics, and
  Extra High passed 1/1 validly with no trajectory gaming signal, so it is now a provisional
  artifact-large keep pending the full Extra High gate.
- `support-sla-business-hours` was expanded into a support SLA operations package with account
  entitlements, outage exemptions, escalations, credits, ticket outputs, account summaries, and
  breach summaries. Two early floor probes exposed prompt ambiguities and were excluded. After
  clarification, `gpt-5.4-mini[low]` passed 1/1 with a general solution, so it was replaced by
  expanded `repo-observability-coverage-audit` in the active AL-2 slot. Extra High was not run on
  the saturated SLA version.

## Calibration Disposition

These labels are funnel decisions, not final benchmark labels. `gpt-5.5[medium]` is retained only
as historical low-spend smoke evidence. The ceiling column below is the corrected
`gpt-5.5[extra_high]` probe. Every survivor still needs the full formal Extra High gate and bridge
validation before it can become an official ShallowSWE v1 medium or large task.

| Slot | Task | Category | Metadata size | Codex floor | Extra High probe | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| CM-1 | `retry-policy-migration` | code | medium | 3/3, small | not run | Too easy; reshape/archive |
| CM-2 | `notification-locale-fallback` | code | medium | 3/3, small | not run | Too easy; reshape/archive |
| CL-1 | `dispatch-planner-split-parity` | code | large | 3/3, small | not run | Too easy for large; reshape/archive |
| CL-2 | `invoice-multi-source-merge` | code | large | 0/2 current after bridge, 1/3 prior | 1/1 valid | Keep provisional large; full Extra High gate pending |
| CL-3 | `seat-compliance-admin-console` | code | large | 0/1 fair after repairs | 1/1 valid | Keep provisional large; full Extra High gate + independent alt pending |
| CL-4 | `feature-entitlements-admin-screen` | code | large | 0/2 current after bridge, 2/3 prior | 1/1 valid | Keep provisional large; full Extra High gate pending |
| CL-5 | `renewal-risk-admin-screen` | code | large | 0/2 after expansion + bridge, 2/3 prior | 1/1 valid after expansion | Keep provisional large; full Extra High gate + independent alt pending |
| AM-1 | `access-log-sessionize` | artifact | medium | 3/3, small | not run | Too easy; reshape/archive |
| AM-2 | `billing-proration-schedule` | artifact | medium | 3/3, small | not run | Too easy; reshape/archive |
| AL-1 | `privacy-retention-evidence-package` | artifact | large | 0/1 fair after fresh authoring | 1/1 valid Extra High | Keep provisional artifact large; full Extra High gate pending |
| AL-2 | `repo-observability-coverage-audit` | artifact | large | 0/1 fair after remediation expansion, 1/1 prior smaller contract | 1/1 valid Extra High | Keep provisional artifact large; full Extra High gate pending |
| CL-6 | `customer-health-dashboard-screen` | code | large | 0/1 fair after recovery/export expansion | 1/1 valid after export verifier repair | Keep provisional large; full Extra High gate + independent alt pending |
| AL-4 | `vendor-risk-evidence-package` | artifact | large | 0/1 fair after fresh authoring | 1/1 valid Extra High | Keep provisional artifact large; full Extra High gate pending |
| WL-4 | `incident-comms-pipeline` | workflow | large | 0/1 fair after replay/API-call-log repair | 1/1 valid Extra High retry at 1200s | Keep provisional workflow large; full Extra High gate pending |
| WM-1 | `ticket-bulk-triage` | workflow | medium | 3/3, small | not run | Too easy; reshape/archive |
| WL-5 | `status-fanout-reconcile` | workflow | large | 0/1 fair after status/gate/notification expansion | 1/1 valid Extra High | Keep provisional workflow large; full Extra High gate pending |
| WM-3 | `ticket-update-dont-duplicate` | workflow | medium | 1/1 after prompt clarification, 0/4 prior | not run after clarification | Too easy after clarification; reshape/archive |
| WL-1 | `release-train-reconcile` | workflow | large | 0/1 after promotion expansion, 1/2 prior | 1/1 valid after prompt repair | Keep provisional workflow large; full Extra High gate pending |
| WL-2 | `tenant-offboarding-reconcile` | workflow | large | 0/1 after integration/billing expansion | 1/1 valid Extra High | Keep provisional workflow large; full Extra High gate pending |
| WL-3 | `config-key-rollover` | workflow | large | 1/1 latest, 2/3 prior | 1/1 valid | Too easy for large after repair; reshape/archive |

## Cards

### CM-1 `retry-policy-migration` (code / medium / L2)

Grow the `retry_parser` fixture into a small package (parser, policy, scheduler, CLI, ~10 files).
Migrate from fixed-delay retries to a spec'd backoff schedule (deterministic formula, no jitter,
table given in the instruction) while keeping the legacy `delay_seconds` column and CLI output
byte-stable for rows that never retry. Verifier re-checks legacy behavior alongside new schedule.
Floor failure hypothesis: patches the parser, misses the scheduler and CLI touch points.
Pre-registered bands: formal ceiling 75-100%, floor 30-70%.

### CM-2 `notification-locale-fallback` (code / medium / L3)

Extend the notifications package with a locale fallback chain (`de-AT -> de -> default`), message
catalogs as data files, and a spec'd escaping rule for HTML. Default-locale output must remain
byte-identical to the current renderers; verifier diffs golden outputs plus new-locale cases.
Floor failure hypothesis: breaks default-locale parity while wiring the fallback.
Pre-registered bands: formal ceiling 75-100%, floor 30-70%.

### CL-1 `dispatch-planner-split-parity` (code / large / L3 + L1)

Grow `dispatch_app` to ~40 files with a monolithic planner. Split it into a spec'd filter-pipeline
layout (module names given) with output parity on a visible golden corpus — except one documented
bug (an ordering defect on a boundary case) that must be fixed, not preserved. Verifier runs the
corpus, the bug case, and hidden orders.
Floor failure hypothesis: parity breaks during the move, or the bug is faithfully preserved.
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.

### CL-2 `invoice-multi-source-merge` (code / large / L4)

The invoice importer gains two more input sources (API export JSON, legacy fixed-width) with a
spec'd precedence order, dedupe key, currency normalization table, and rejection rules. Existing
CSV behavior and CLI output stay stable; a focused regression test must be authored (the suite
already has this pattern in `invoice-cli-regression-test-fix`). Verifier checks all sources,
precedence conflicts, and the authored test's existence and honesty.
Floor failure hypothesis: satisfies most constraints, loses one under conjunction (usually
precedence x normalization interactions).
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.
Current status: Extra High n=1 passed validly. The first current low floor failed fairly by leaving
legacy dates unnormalized. The bridge low floor also failed fairly after implementing all three
sources and a CSV-only regression test: rejected rows were sorted `legacy,csv,api` instead of the
required `api,csv,legacy` order on visible and hidden fixtures. Keep as provisional large pending
the full Extra High gate.

### AM-1 `access-log-sessionize` (artifact / medium / L7)

Multi-file access logs, out of chronological order, spanning a day boundary. Emit sessions per
client with a 15-minute idle window, spec'd session-id rule, and spec'd tie-breaks. All columns
and rounding stated in the instruction. Hidden rerun uses different boundaries.
Floor failure hypothesis: merge/sort/boundary interactions produce off-by-one sessions.
Pre-registered bands: formal ceiling 75-100%, floor 30-70%.

### AM-2 `billing-proration-schedule` (artifact / medium / L4)

From subscription events (upgrades, downgrades, cancellations mid-period), produce a proration
schedule with spec'd day-count convention, rounding rule, ordering, and credit handling. Every
rule is stated; there are eight of them and they all interact.
Floor failure hypothesis: any one rule dropped under conjunction.
Pre-registered bands: formal ceiling 75-100%, floor 30-70%.

### AL-1 `privacy-retention-evidence-package` (artifact / large / L7 + L5 + L4)

Fresh synthetic multi-service privacy retention evidence package: dataset catalogs, systems,
retention policy limits, purge/export jobs, source-code annotations, legal holds, downstream
propagation, exemptions, incidents, owner rollups, and a remediation plan. It replaces
`ledger-restatement-audit`, whose expanded controls package still saturated the low floor.
Floor failure hypothesis: the first obvious implementation joins the core tables but misses one of
the compounded policy/action/evidence contracts, especially action label mapping, stale job windows,
downstream propagation, legal holds, or owner/summary counters.
Pre-registered bands: formal ceiling 75-100% on `openai/gpt-5.5[extra_high]`, floor 0-40%.
Current status: reference replay passed. The low-floor `gpt-5.4-mini[low]` probe failed fairly after
building a general audit script: visible and hidden schema checks passed, but visible verification
caught the internal `legal_hold` action code instead of the documented `review active legal hold`
label. Extra High n=1 passed visible and hidden verification with a general builder, `py_compile`,
schema/header assertions, and deterministic rerun hash checks. Command audit found no hidden-test,
verifier, reward, solution, `/tmp/shallowswe-pier`, hardcoding, or gaming signal. Keep as
provisional artifact-large pending the full Extra High gate.

### AL-2 `repo-observability-coverage-audit` (artifact / large / L7 + L5 + L4)

Expanded synthetic multi-service repository observability package: route metadata, source telemetry,
dashboards, alerts, incidents, owners, exemptions, downstream service edges, runbook freshness,
recent deploy rollback readiness, owner rollups, and a remediation plan. The prior route-scoped
version was too easy after verifier repair; this expansion adds cross-repository governance state
and an additional artifact output. It replaces `support-sla-business-hours`, which was also too easy
for artifact-large after the SLA operations expansion and prompt clarifications.
Floor failure hypothesis: the first obvious implementation handles route telemetry but misses one of
downstream trace propagation, stale runbooks, rollback readiness, remediation priority/due-date
ordering, or the expanded owner/summary counters.
Pre-registered bands after expansion: formal ceiling 75-100% on
`openai/gpt-5.5[extra_high]`, floor 0-40%.
Current status: reference replay passed. The first low-floor attempt is excluded for tier-threshold
prompt ambiguity, and the second is excluded for trailing-markdown verifier brittleness. After
those repairs, the low floor failed fairly on explicit board action priority. Extra High n=1
passed visible and hidden verification with a general repository audit script; command audit found
no hidden-test, verifier, reward, solution, `/tmp/shallowswe-pier`, hardcoding, or gaming signal.
Keep as provisional artifact-large pending the full Extra High gate.

### WM-1 `ticket-bulk-triage` (workflow / medium / L5)

Forty tickets in mock API state, a spec'd triage policy (priority rules with precedence), partial
prior state (some tickets already correctly triaged). Apply the policy idempotently: update only
what the policy changes, never create duplicates, and keep the call log minimal (spec'd: one call
per changed ticket, none for unchanged). Structural verifier per `ticket-update-dont-duplicate`.
Floor failure hypothesis: redundant calls or missed precedence cases at volume.
Pre-registered bands: formal ceiling 75-100%, floor 30-70%.

### WL-5 `status-fanout-reconcile` (workflow / large / L5 + L6 + L4)

Reconcile build results across posted statuses, deployment gates, owner notifications,
`calls.log`, and `release_summary.json`. The workflow must preserve unrelated API state, avoid
duplicate notifications, compute blocked and ready gates from required-suite rules, keep exact call
ordering across status, gate, and notification phases, and replay idempotently.
Floor failure hypothesis: the agent handles most state reconciliation but misses one interaction
between gate blockers, notification dedupe, call ordering, or replay summary counts.
Pre-registered bands after expansion: formal ceiling 75-100% on
`openai/gpt-5.5[extra_high]`, floor 0-40%.
Current status: Expanded from the smaller WM-2 medium candidate on 2026-07-07. The first low-floor
probe is excluded because a verifier fixture-isolation bug copied already-mutated visible state
from `/app`. The repaired low-floor probe failed fairly on explicit notification call ordering,
while the Extra High n=1 probe passed visible, hidden, and replay-idempotency checks with no
hardcoding or verifier gaming signal. Keep as provisional workflow-large pending the full Extra
High gate. Medium rows are smoke-only and cannot accept this task.

### WL-1 `release-train-reconcile` (workflow / large / L6 + L5)

Mock release state: branches, tags, changelog, status checks, release manifests, and promotion
readiness records, divergent from a spec'd target release plan. Bring state to target under
ordering constraints (tag only after checks, changelog before manifest, manifest before promotion
records, no destructive operations, spec'd audit grammar). The expansion gives the task a broader
workflow surface than the original single-plan reconciler.
Floor failure hypothesis: right operations, wrong phase order, missed promotion-manifest
interaction, or destructive shortcuts.
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.
Current status: Expanded on 2026-07-07 with release manifest and promotion-ring readiness
requirements. The post-expansion low floor failed fairly after implementing most of the workflow:
it ran promotion checks after `update_changelog`, violating the explicit phase ordering on visible
and hidden fixtures. The first Extra High attempt solved the workflow but failed on an
underspecified audit `detail` type, so the prompt was clarified. The corrected Extra High n=1
passed with a generalized, plan-driven implementation and hidden-fixture success. Keep as
provisional workflow large pending the full Extra High gate.

### WL-2 `tenant-offboarding-reconcile` (workflow / large / L5 + L6)

From an operations state store, process approved tenant-offboarding requests across tenants,
memberships, sessions, API keys, invites, integrations, billing accounts, exports, tickets, legal
holds, call logs, and audit logs. The workflow must preserve replay safety, process requests in a
specified order, avoid duplicate operations, honor legal-hold export retention, quiesce
tenant-facing integrations, lock or close billing, and emit an offboarding summary. It replaced
`incident-comms-pipeline` after a repaired Extra High timeout, but the later 1200s incident-comms
retry passed and incident-comms is now active as WL-4.
Floor failure hypothesis: a low floor model mutates most state but misses idempotence, legal-hold
exceptions, call-log sequencing, or partial prior state.
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.
Current status: Authored on 2026-07-07 as the WL-2 replacement, then expanded after the repaired
low floor passed the smaller contract. The old repaired low-floor success is superseded for sizing.
The current contract adds `integrations.json` and `billing_accounts.json` phases with visible and
hidden verifier coverage. Reference replay passes visible and hidden idempotence checks. The fresh
`gpt-5.4-mini[low]` probe failed fairly: it implemented most phases but did not persist
`runbook.json`, leaving eligible requests approved. The formal Extra High N=1 probe passed with a
generic reconciler that persisted all state files, passed visible and hidden verifier checks, and
showed no hardcoding or verifier gaming. Keep as provisional workflow large pending the full Extra
High gate.

### CL-3 `seat-compliance-admin-console` (code / large / L1 + L2 + L4)

Repo-scale web feature task: add a seat-compliance admin console across route tables, navigation,
selectors, rendering, fixture data, owner aggregation, overage review, an action log, JSON export,
and regression coverage in a broad static app. The contract includes four routes
(`/seat-compliance`, `/seat-compliance/overages`, `/seat-compliance/owner-queue`, and
`/seat-compliance/action-log`) plus subscriptions, plan limits, allocations, users, invitations,
exceptions, tickets, account rows, overage rows, owner rollups, action rows, and export payloads.
Floor failure hypothesis: implements visible routing and markup but misses a hidden cross-source
invariant such as latest allocation selection, expired-vs-pending invitations, active exceptions,
all-applicable reason codes, owner escalation aggregation, or regression tests.
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.
Current status: Authored on 2026-07-07 as the CL-3 replacement after
`customer-health-dashboard-screen` saturated low floor after verifier repair, then expanded with an
action-log screen and JSON export contract. Two early expanded runs exposed verifier/prompt contract
issues: metric-label parsing and an ambiguous owner-escalations metric; the first repaired Extra
High run then exposed an export verifier mismatch where the verifier expected an internal
`account_id` field not required by the prompt. After those repairs, the low floor failed fairly on
`data-account-id` semantics after implementing the feature and passing its own tests. The corrected
Extra High n=1 passed validly: the agent inspected the app and fixtures, added a shared selector,
four screens, route/nav/CLI export wiring, CLI-level regression tests, visible HTML/export smoke
checks, and passed hidden fixtures. No hardcoding or verifier gaming was found. Keep as provisional
code-large pending the full Extra High gate and independent alternate solution.

### CL-4 `feature-entitlements-admin-screen` (code / large / L1 + L4)

Add an entitlements administration screen across app routing, permission selectors, UI rendering,
navigation, and tests. The task forces cross-file feature integration rather than isolated bug
fixing.
Floor failure hypothesis: solves the obvious screen but misses edge-state rendering, selection
logic, or coverage requirements.
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.
Current status: Extra High n=1 passed validly. The first current low floor failed fairly on hidden
override metric semantics after visible tests passed. The bridge low floor also failed fairly after
implementing both screens and passing its own visible regression tests: it emitted only the priority
`subscription_not_serviceable` reason code and missed the independently applicable
`usage_over_limit` reason code on visible and hidden fixtures. Keep as provisional large pending
the full Extra High gate.

### CL-5 `renewal-risk-admin-screen` (code / large / L1 + L4)

Add a renewal-risk admin area with risk, concession, and owner-queue screens plus shared selectors
in an existing operations app. The expanded task joins accounts, contracts, usage, tickets,
concessions, segment policies, engagements, and renewal plan items, then keeps routing, nav,
fixture contracts, and regression tests consistent.
Floor failure hypothesis: gets the visible screens working but misses an owner-queue aggregation
or a hidden cross-source policy interaction.
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.
Current status: Expanded on 2026-07-07. The first low floor failed fairly by computing
`owners-with-escalations` as 0 even when visible and hidden fixtures required escalations. The
bridge low floor also failed fairly: the agent implemented the broad three-screen feature and
passed its own visible tests, but the verifier caught `risk_reasons` being priority-only instead of
all applicable reason codes on visible and hidden fixtures. Extra High n=1 passed validly with a
generalized implementation and hidden fixture success. Keep as provisional large; still needs the
full Extra High gate and a materially independent alternate solution.

### CL-6 `customer-health-dashboard-screen` (code / large / L1 + L2 + L4)

Repo-scale web feature task: expand the customer-health command center across route tables,
navigation, shared selectors, four screen modules, fixture joins, regression tests, and CLI JSON
export. The contract now includes `/customer-health`, `/customer-health/actions`,
`/customer-health/owner-queue`, `/customer-health/recovery-plan`, plus
`--export-customer-health`.
Floor failure hypothesis: implements the visible screens but misses one cross-source invariant in
the recovery-plan/export layer, such as recovery-stage priority, blocker counts, executive-touch
logic, action due dates, owner rollups, or export summary parity.
Pre-registered bands: formal ceiling 75-100% on `openai/gpt-5.5[extra_high]`, floor 0-40%.
Current status: The prior three-route expansion saturated low floor after verifier repair and is
superseded. This recovery/export expansion was authored on 2026-07-07. The low-floor run failed
fairly: it implemented the feature but missed the documented `engagement_restart` recovery stage
and export details. The first Extra High run exposed an invalid verifier expectation around export
dashboard row fields; after repairing the verifier to match the written JSON export contract, Extra
High n=1 passed validly with shared selector/export logic, four screens, route/nav/CLI integration,
regression tests, and hidden fixture success. Keep as provisional code-large pending the full Extra
High gate. Medium rows are smoke-only and cannot accept this task.

### AL-4 `vendor-risk-evidence-package` (artifact / large / L7 + L5 + L4)

Fresh synthetic repository-scale vendor-risk evidence package: vendor inventory, production
services, contracts, current and stale security evidence, subprocessors, incidents, exceptions,
source-code vendor annotations, owner rollups, renewal action planning, and summary counters. It
replaces `ledger-schema-upgrade`, whose expanded v4 ledger evidence package still saturated the
low floor after contract repair.
Floor failure hypothesis: the first obvious implementation joins inventory, contracts, and evidence
but misses one interaction between source text evidence, renewal windows, active exceptions,
regional review, subprocessors, or action/evidence ordering.
Pre-registered bands: formal ceiling 75-100% on `openai/gpt-5.5[extra_high]`, floor 0-40%.
Current status: reference replay passed. The low-floor `gpt-5.4-mini[low]` probe failed fairly
after building a general script: it treated integration path presence as source evidence and missed
the written rule that source evidence files must contain the exact vendor id in file text, failing
visible `chatly` and hidden `carebot` production-source-reference checks. Extra High n=1 passed
visible and hidden verification with a general builder, `py_compile`, schema/header checks, JSON
parsing, and deterministic rerun hash checks. Command audit found no hidden-test, verifier, reward,
solution, `/tmp/shallowswe-pier`, hardcoding, or gaming signal. Keep as provisional artifact-large
pending the full Extra High gate.

### WL-4 `incident-comms-pipeline` (workflow / large / L5 + L6 + L4)

Reconcile statuspage-style component, incident, and subscriber-notification state from a
deterministic timeline. The command must sort events, create or update incidents, dedupe update
keys, preserve durable replay state, resolve stale incidents, enqueue severity-filtered
notifications, preserve API call-log semantics for the current run, and write ordered audit JSONL.
Floor failure hypothesis: the agent handles obvious incident/update paths but misses replay
idempotency, first-run component transitions, unchanged-component notifications, stale resolution,
or call-log semantics under partial prior state.
Pre-registered bands after repair: formal ceiling 75-100% on `openai/gpt-5.5[extra_high]`, floor
0-40%.
Current status: Visible replay/API-call-log coverage was added after earlier fair failures. The
repaired low floor failed fairly: it passed visible tests but skipped first-run component
transitions and notified an unchanged component on hidden checks. The first repaired Extra High
attempt timed out at 900s before verifier, so the task timeout was raised to 1200s to match other
large candidates. The 1200s Extra High retry passed visible and hidden verifier checks with a
generalized reconciler, `py_compile`, visible unittest discovery, and manual replay checks. Command
audit found no hidden-test, verifier, reward, solution, `/tmp/shallowswe-pier`, hardcoding, or
gaming signal. Keep as provisional workflow large pending the full Extra High gate.

### WM-3 `ticket-update-dont-duplicate` (workflow / medium / L5)

Find existing ticket state and update it instead of creating duplicates. This remains metadata
medium, but the Codex floor result was 0/3 with legitimate failures, so it is a candidate for
promotion only after bridge/formal validation.
Floor failure hypothesis: creates a duplicate or updates the wrong matching ticket under partial
state.
Pre-registered bands: formal ceiling 75-100%, floor 30-70% unless promoted after bridge evidence.
Current status: Extra High n=1 passed and latest low floor failed on the hidden anti-hardcoding
case, but the prompt named the visible fixture ticket id. After tightening the instruction to require
finding the matching open ticket without assuming a fixed id, the low floor passed 1/1 validly with
a generic update script and hidden verifier success. Treat as too easy for medium after
clarification; do not spend Extra High on this version.

### WL-3 `config-key-rollover` (workflow / large / L2 + L3)

Roll a dispatch visibility config key across runtime config, fixtures, CLI help, docs, and
compatibility aliases. The correct implementation has to preserve legacy behavior while applying
new precedence rules across several call sites.
Floor failure hypothesis: migrates the primary code path but misses docs/help/fixtures or alias
precedence.
Pre-registered bands: formal ceiling 75-100%, floor 0-40%.
Current status: Packaging and fixture scope were repaired, and Extra High n=1 passed validly with
a generalized config/planner/fixture/docs migration. The latest low floor also passed in 5 steps
with a generalized solution, so this is too easy for the large tranche after repair. Reshape,
archive, or demote before rerunning.

## Authoring order

Current provisional large keeps are `invoice-multi-source-merge`,
`seat-compliance-admin-console`, `feature-entitlements-admin-screen`,
`renewal-risk-admin-screen`, `customer-health-dashboard-screen`,
`privacy-retention-evidence-package`, `repo-observability-coverage-audit`,
`vendor-risk-evidence-package`, `release-train-reconcile`, `tenant-offboarding-reconcile`,
`status-fanout-reconcile`, and `incident-comms-pipeline`. Run the full Extra High gate before
official admission, and keep expanding or replacing the remaining weak artifact/workflow large
slots before broad scoring.

The first `repo-observability-coverage-audit` contract was too easy after verifier repair, but the
expanded remediation version is now the active AL-2 artifact-large keep. `audit-log-normalization`
was also too easy after verifier repair and has been replaced by the expanded
`deployment-approval-reconcile`, which also passed the low floor and is too easy.
The expanded `ledger-restatement-audit` controls package also passed the low floor, so it remains a
reshape/archive item rather than an artifact-large keep; `privacy-retention-evidence-package`
replaces it in AL-1 with fair floor-fail and valid Extra High-pass evidence. Reshape or demote
`ledger-schema-upgrade`; it is not a strong large task as written. `vendor-risk-evidence-package`
replaces it in AL-4 with fair floor-fail and valid Extra High-pass evidence. Keep
`ticket-update-dont-duplicate` in the medium bridge lane unless it is expanded. Keep expanded
`tenant-offboarding-reconcile` and `status-fanout-reconcile` as provisional workflow large; prior
repaired low-floor passes only apply to their smaller pre-expansion contracts, while the expanded
contracts now have fair floor failure and valid Extra High pass evidence.
Keep `incident-comms-pipeline` as the active WL-4 provisional workflow-large candidate after its
1200s Extra High retry. Reshape or archive `config-key-rollover` and the superseded
`deployment-approval-reconcile` candidate.
Saturated probes should only be revisited if their fixture scope is materially expanded.

# Medium/Large Refill Candidate Cards

Status: draft for review. Written 2026-07-05, while the post-amendment floor recalibration
(`configs/shallowswe-floor-recal-oneshot-n3.json`) is in flight.

## Why this file exists

The 2026-07-05 spec amendments removed the last spec-ambiguity difficulty from the frozen 18-task
suite. The clean preview run (195/195 solved, all 10 panel configs) and the pending floor
recalibration are expected to confirm that every current task sits in the small band. That vacates
the medium and large cells of the 3x3 category/size matrix.

This file proposes 12 candidates: 2 per vacant cell. Difficulty must come from engineering
surface, never from spec tightness. Every candidate keeps the ceiling invariant — a frontier model
should one-shot it by reading the repo — and targets floor thrash through one named lever.

## Design rules (carried over, plus lessons from 2026-07-05)

- Full output contracts in the instruction. If the verifier asserts it, the instruction or the
  visible repo derives it. No guessing games; we measured what those cost.
- Verifiers run on fresh seeded roots (stateless), assert structurally where prose is not the
  contract, and rerun on hidden inputs to catch hardcoding.
- Two materially different correct solutions must pass before admission.
- Two-sided gate, pre-registered per card: ceiling one-shot >= 75%; floor one-shot inside the
  target band (medium 30-70%, large 0-40%) measured on `panels/shallowswe-calibration-v0.1.json`.
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
| AL-1 | `ledger-restatement-audit` | artifact | large | L5 + L7 |
| AL-2 | `support-sla-business-hours` | artifact | large | L7 |
| WM-1 | `ticket-bulk-triage` | workflow | medium | L5 |
| WM-2 | `status-fanout-reconcile` | workflow | medium | L5 |
| WL-1 | `release-train-reconcile` | workflow | large | L6 + L5 |
| WL-2 | `incident-comms-pipeline` | workflow | large | L4 + L6 |

## Cards

### CM-1 `retry-policy-migration` (code / medium / L2)

Grow the `retry_parser` fixture into a small package (parser, policy, scheduler, CLI, ~10 files).
Migrate from fixed-delay retries to a spec'd backoff schedule (deterministic formula, no jitter,
table given in the instruction) while keeping the legacy `delay_seconds` column and CLI output
byte-stable for rows that never retry. Verifier re-checks legacy behavior alongside new schedule.
Floor failure hypothesis: patches the parser, misses the scheduler and CLI touch points.
Pre-registered bands: ceiling 75-100%, floor 30-70%.

### CM-2 `notification-locale-fallback` (code / medium / L3)

Extend the notifications package with a locale fallback chain (`de-AT -> de -> default`), message
catalogs as data files, and a spec'd escaping rule for HTML. Default-locale output must remain
byte-identical to the current renderers; verifier diffs golden outputs plus new-locale cases.
Floor failure hypothesis: breaks default-locale parity while wiring the fallback.
Pre-registered bands: ceiling 75-100%, floor 30-70%.

### CL-1 `dispatch-planner-split-parity` (code / large / L3 + L1)

Grow `dispatch_app` to ~40 files with a monolithic planner. Split it into a spec'd filter-pipeline
layout (module names given) with output parity on a visible golden corpus — except one documented
bug (an ordering defect on a boundary case) that must be fixed, not preserved. Verifier runs the
corpus, the bug case, and hidden orders.
Floor failure hypothesis: parity breaks during the move, or the bug is faithfully preserved.
Pre-registered bands: ceiling 75-100%, floor 0-40%.

### CL-2 `invoice-multi-source-merge` (code / large / L4)

The invoice importer gains two more input sources (API export JSON, legacy fixed-width) with a
spec'd precedence order, dedupe key, currency normalization table, and rejection rules. Existing
CSV behavior and CLI output stay stable; a focused regression test must be authored (the suite
already has this pattern in `invoice-cli-regression-test-fix`). Verifier checks all sources,
precedence conflicts, and the authored test's existence and honesty.
Floor failure hypothesis: satisfies most constraints, loses one under conjunction (usually
precedence x normalization interactions).
Pre-registered bands: ceiling 75-100%, floor 0-40%.

### AM-1 `access-log-sessionize` (artifact / medium / L7)

Multi-file access logs, out of chronological order, spanning a day boundary. Emit sessions per
client with a 15-minute idle window, spec'd session-id rule, and spec'd tie-breaks. All columns
and rounding stated in the instruction. Hidden rerun uses different boundaries.
Floor failure hypothesis: merge/sort/boundary interactions produce off-by-one sessions.
Pre-registered bands: ceiling 75-100%, floor 30-70%.

### AM-2 `billing-proration-schedule` (artifact / medium / L4)

From subscription events (upgrades, downgrades, cancellations mid-period), produce a proration
schedule with spec'd day-count convention, rounding rule, ordering, and credit handling. Every
rule is stated; there are eight of them and they all interact.
Floor failure hypothesis: any one rule dropped under conjunction.
Pre-registered bands: ceiling 75-100%, floor 30-70%.

### AL-1 `ledger-restatement-audit` (artifact / large / L5 + L7)

Twelve monthly ledger files plus a corrections file with late-arriving amendments that restate
prior months. Produce restated rollups and an audit trail listing every correction applied, in
spec'd order, idempotently (re-running on already-restated outputs must be a no-op). Predecessor
`ledger-schema-upgrade` was demoted for saturating; this version compounds volume, restatement,
and idempotency.
Floor failure hypothesis: double-applies corrections or loses audit ordering at volume.
Pre-registered bands: ceiling 75-100%, floor 0-40%.

### AL-2 `support-sla-business-hours` (artifact / large / L7)

SLA recomputation under a business-hours calendar: working windows, listed holidays, clock pauses
while tickets sit in `waiting-on-customer`. Conventions fully spec'd (inclusive/exclusive bounds,
timezone, rounding). Hidden rerun moves the holidays.
Floor failure hypothesis: boundary interactions (pause spanning a holiday spanning a weekend).
Pre-registered bands: ceiling 75-100%, floor 0-40%.

### WM-1 `ticket-bulk-triage` (workflow / medium / L5)

Forty tickets in mock API state, a spec'd triage policy (priority rules with precedence), partial
prior state (some tickets already correctly triaged). Apply the policy idempotently: update only
what the policy changes, never create duplicates, and keep the call log minimal (spec'd: one call
per changed ticket, none for unchanged). Structural verifier per `ticket-update-dont-duplicate`.
Floor failure hypothesis: redundant calls or missed precedence cases at volume.
Pre-registered bands: ceiling 75-100%, floor 30-70%.

### WM-2 `status-fanout-reconcile` (workflow / medium / L5)

A queue of build results against existing posted statuses. Post only missing or changed statuses,
correct stale ones, never repost identical state. Extends `post-build-status` from one result to
a reconciliation over ~25 with prior state.
Floor failure hypothesis: reposts unchanged statuses or misses stale corrections.
Pre-registered bands: ceiling 75-100%, floor 30-70%.

### WL-1 `release-train-reconcile` (workflow / large / L6 + L5)

Mock release state: branches, tags, changelog, status checks — divergent from a spec'd target
release plan. Bring state to target under ordering constraints (tag only after checks pass,
changelog before tag, no destructive operations, spec'd call-log grammar). The historical
`ticket-state-reconcile` card notes this reconcile shape "produced a real large workflow signal."
Floor failure hypothesis: right operations, wrong order, or destructive shortcuts.
Pre-registered bands: ceiling 75-100%, floor 0-40%.

### WL-2 `incident-comms-pipeline` (workflow / large / L4 + L6)

From an incident timeline, drive mock statuspage state: component statuses, incident updates from
spec'd templates, resolution of stale incidents, strict dedupe, spec'd update ordering. Many
small artifacts that must stay mutually consistent.
Floor failure hypothesis: consistency between artifacts drifts across the sequence.
Pre-registered bands: ceiling 75-100%, floor 0-40%.

## Authoring order

Build one probe candidate per category first — suggested: CM-1, AM-1, WM-2 (cheapest fixtures to
grow) — run the two-sided gate on those three, and use the measured floor bands to tune fixture
scale before building the remaining nine. If the floor saturates all three probes, the levers need
to be compounded harder before authoring continues; that is a cheaper lesson on three tasks than
on twelve.

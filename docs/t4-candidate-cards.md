# Historical T4 Candidate Cards

Status: deprecated as active taxonomy. ShallowSWE now uses the public fields
`category = code|artifact|workflow` and `size = small|medium|large`. These notes are retained only
as calibration history for tasks that have since been folded into the large size band.

These cards defined the first proposed T4 task set. `ticket-state-reconcile`,
`config-key-rollover`, `status-terminal-parity`, and `ledger-schema-upgrade` now exist under
`tasks/`. Current acceptance happens through the small/medium/large calibration protocol, not
through a T4 gate.

The useful idea from this file is the crossover pattern: find routine tasks where cheap or
low-effort rows stop being the cheapest path to a correct result.

## Design Target

T4 tasks should be routine but stateful:

- no deep architecture or algorithm insight,
- more constraints to keep in working memory,
- more repo or artifact state to reconcile,
- more edge cases that compound,
- verifier checks broad enough to accept alternate correct implementations.

The expected failure mode for weaker rows is flailing, partial completion, duplicated work, missed compatibility behavior, or broken adjacent behavior.

## Admission Rules

Each historical card pre-registered a calibration hypothesis before any model run:

- expected pass-rate band for floor or weak rows,
- expected pass-rate band for frontier/top-gated rows,
- predicted cheapest-correct row class,
- demotion rule if the task saturates.

Calibration uses the current versioned anchor panel, `panels/shallowswe-calibration-v0.1.json`.
Calibration rollouts are quarantined from published leaderboard results.

Every accepted task must pass the verifier with two materially different correct solutions: the
reference solution and an alternate solution with different structure or helper decomposition.

Under the current protocol, if every scored floor candidate passes at saturation, the task is moved
to small/medium or reshaped. It is not kept as a special tier.

Issue links and public benchmark links are not published in this file. They may live in a private
authoring log only. Public cards record the abstract shape and contamination notes.

`expected_engineer_minutes` is an authoring heuristic, not a measured benchmark field.

## Candidate Set

| Slot | Candidate ID | Category | Shape | Status |
| --- | --- | --- | --- | --- |
| T4-FIX-001 | `status-terminal-parity` | Fix | `parallel-fix` | saturated N=1 probe |
| T4-TRANSFORM-001 | `ledger-schema-upgrade` | Transform | `schema-upgrade-pipeline` | demoted to T3 after N=15 calibration |
| T4-OPERATE-001 | `config-key-rollover` | Operate | `cross-cutting-rename` | saturated N=1 plumbing probe |
| T4-INVOKE-001 | `ticket-state-reconcile` | Invoke | `reconcile-states` | folded into large workflow |

The mock API reconciliation pattern produced a real large workflow signal. Smaller workflow tasks
now live in the default 3x3 basket.

## T4-FIX-001: `status-terminal-parity`

```toml
category = "fix"
tier_hypothesis = "t4"
maintenance_type = "corrective"
shape = "parallel-fix"
delegated_work_unit = "make terminal order status handling consistent across import, webhook, and report paths"
expected_touchpoints = 10
expected_engineer_minutes = 50
verifier_shape = "behavior tests across three entry points plus regression checks for existing statuses"
floor_pass_rate_hypothesis = "40-75%"
top_pass_rate_hypothesis = ">=80%"
predicted_cheapest_correct_row = "frontier-low if floor rows miss one entry point"
demote_if = "all scored rows pass at saturation"
```

### Work Packet

A small fulfillment package receives order status from three paths:

- CSV imports from operations,
- webhook JSON from a carrier,
- an admin repair CLI.

The repo already has a status-normalization helper, but two paths bypass part of it. A new terminal status, `return_to_sender`, must behave like existing terminal statuses in all three paths. The old carrier spelling `rts` must remain accepted as an alias.

The agent must repair the shared behavior without breaking existing statuses such as `delivered`, `cancelled`, `hold`, and `pending_review`.

### Why T4

This is not conceptually hard, but it is easy to finish only one path. Correctness requires tracing a shared rule through import, webhook, reporting, and CLI surfaces. The card is acceptable only if existing tests or docs make terminal-status semantics derivable from the base repo, so hidden tests are not asking the agent to guess.

### Verifier Contract

Required checks:

- Base repo fails on `return_to_sender` in all three entry points.
- Reference solution passes three clean runs.
- Hidden fixtures exercise all three entry points.
- Regression checks cover existing terminal and non-terminal statuses.
- Public CLI behavior remains stable.
- No exact helper/function implementation is required.

Pass-to-pass checks:

- `delivered` and `cancelled` remain terminal.
- `hold` and `pending_review` remain non-terminal.
- Existing CSV and webhook happy paths still parse.

Overreach checks:

- Agent must not delete status aliases.
- Agent must not make every unknown status terminal.

### Local Validation

The task now exists under `tasks/status-terminal-parity`. The unmodified base fails the hidden
verifier for the intended missing `return_to_sender` and `rts` behavior. The reference solution
passed three clean verifier runs, an alternate solution passed the same verifier, and Pier oracle
passed through the Docker runner.

### Calibration Outcome

The first N=1 cheap-anchor sweep passed 3/3 rows. The task is marked `probe_saturated_n1` and is
not accepted as T4 without redesign. Gemini 3.5 Flash medium needed 31 turns, so the task remains
useful for flailing analysis, but not for shelf-edge admission.

### Expected Weak-Row Failure

- Fixes CSV import but misses webhook or admin CLI.
- Adds status-specific branching in one surface instead of shared normalization.
- Breaks unknown-status validation.
- Changes report output ordering or CLI command names.

### Contamination Notes

Abstract shape only: copied status semantics across multiple ingestion surfaces. No issue text,
patch, tests, filenames, or domain data should be copied.

## T4-TRANSFORM-001: `ledger-schema-upgrade`

```toml
category = "transform"
tier_hypothesis = "t4"
maintenance_type = "adaptive"
shape = "schema-upgrade-pipeline"
delegated_work_unit = "upgrade mixed billing inputs into a v3 ledger with rejects and summary totals"
expected_touchpoints = 12
expected_engineer_minutes = 55
verifier_shape = "canonicalized output comparison for intermediate and final artifacts"
floor_pass_rate_hypothesis = "25-60%"
top_pass_rate_hypothesis = ">=80%"
predicted_cheapest_correct_row = "frontier-low or medium effort row that avoids reruns"
demote_if = "all scored rows pass at saturation or failures are due to ambiguous spec"
```

### Work Packet

A local billing migration command reads mixed v1/v2 operational files and writes a v3 ledger package:

- `accounts.csv`,
- `plans.json`,
- `usage.jsonl`,
- `credits.csv`,
- `legacy_adjustments.csv`.

The command must write:

- `normalized_events.jsonl`,
- `ledger.csv`,
- `rejects.csv`,
- `summary.json`.

Rules are fully specified in the prompt: key joins, amount normalization, credit application order, reject reason codes, and deterministic sorting.

### Why T4

This stays deterministic and clerical, but the state is wide enough that partial solutions are likely. It deliberately tests adherence to a longer local spec, which is a realistic delegated-work pressure when the spec is airtight. This is the strongest first candidate for genuine T4 pass-rate divergence.

### Calibration Outcome

N=15 calibration on `shallowswe-calibration-v0.1` produced anchor pass rates of 0.800, 0.867,
and 0.933. The median pass rate was 0.867, which fails the T4 0.300-0.700 band and fits the T3
0.800-0.950 band. The task is therefore marked `calibrated_t3` and is not accepted as T4.

### Verifier Contract

Required checks:

- Schema validation for every output file.
- Canonicalized comparison for `normalized_events.jsonl`, `ledger.csv`, and `rejects.csv`.
- Canonicalization specifies UTF-8, LF line endings, fixed decimal places, stable column order, and
  deterministic JSON key ordering.
- Summary aggregate checks for count, gross, credit, net, and reject totals.
- Hidden fixtures include records absent from visible examples but covered by prompt rules.
- Ordering is checked only where prompt requires deterministic ordering.

Pass-to-pass checks:

- Existing v1-only migration fixture still works.
- Existing v2-only migration fixture still works.
- Missing optional credits remain valid and do not create rejects.

Overreach checks:

- No extra output columns.
- Unknown account and unknown plan have distinct reject reasons.
- Duplicate usage events are rejected once, not silently deduped into ledger rows.

### Expected Weak-Row Failure

- Produces final ledger but omits intermediate output.
- Applies credits before adjustments or in the wrong scope.
- Handles visible examples but fails hidden mixed-version records.
- Collapses several reject reasons into one generic reason.

### Contamination Notes

Abstract shape only: mixed-version operational files converted into canonical outputs plus rejects.
No issue text, patch, tests, filenames, or domain data should be copied.

## T4-OPERATE-001: `config-key-rollover`

```toml
category = "operate"
tier_hypothesis = "t4"
maintenance_type = "adaptive"
shape = "cross-cutting-rename"
delegated_work_unit = "roll a config key across env, CLI, docs, fixtures, and runtime while preserving the old alias"
expected_touchpoints = 11
expected_engineer_minutes = 50
verifier_shape = "repo end-state checks plus command-level behavior and compatibility alias tests"
floor_pass_rate_hypothesis = "60-95%"
top_pass_rate_hypothesis = ">=80%"
predicted_cheapest_correct_row = "cheap floor row unless precedence or docs/help coupling causes flailing"
demote_if = "frontier-low rows pass near 100% with low turns"
```

### Work Packet

A repo is migrating from a boolean environment flag to an enum config key:

- old: `DISPATCH_INCLUDE_CLOSED=1`,
- new: `DISPATCH_VISIBILITY=active|archived|all`.

The runtime, CLI help, env loader, config dataclass, fixtures, and docs must use the new key. The old key remains a compatibility alias when the new key is absent. If both are present, the new key wins.

The CLI command name and existing output format must stay stable.

### Why T4

This is routine operate work, but it spans several repo surfaces and has precedence behavior. It is likely the cheapest plumbing validation for the T4 pipeline, but may demote to T3 if frontier-low rows clear it at saturation.

### Calibration Outcome

The first N=1 expanded-panel sweep passed 10/10 model configs. No high-N T4 calibration was run
after saturation. The task is marked `probe_saturated_n1` and is not accepted as T4.

### Verifier Contract

Required checks:

- Command behavior for each new enum value.
- Old boolean alias still works when new key is absent.
- New key takes precedence when both are present.
- CLI help/docs checks assert only literal public contract terms required by the prompt:
  `DISPATCH_VISIBILITY`, `active`, `archived`, and `all`.
- Existing command output format remains stable.

Pass-to-pass checks:

- Default behavior remains active-only.
- Existing region/account filters still work.
- Existing old-key-only fixture still passes.

Overreach checks:

- No CLI command rename.
- No broad refactor required.
- No exact documentation prose check beyond presence of the public contract terms.

### Expected Weak-Row Failure

- Implements new key but removes old alias.
- Keeps alias but gives it wrong precedence.
- Fixes tests by special-casing one fixture.
- Updates docs/help but misses runtime config path.

### Contamination Notes

Abstract shape only: config key migration with compatibility alias and precedence rules. No issue
text, patch, tests, filenames, or domain data should be copied.

## T4-INVOKE-001: `ticket-state-reconcile`

```toml
category = "invoke"
tier_hypothesis = "t4"
maintenance_type = "corrective"
shape = "reconcile-states"
delegated_work_unit = "reconcile a local service manifest against a deterministic ticket API"
expected_touchpoints = 9
expected_engineer_minutes = 45
verifier_shape = "mock API final state plus call-log checks for duplicate and destructive actions"
floor_pass_rate_hypothesis = "35-70%"
top_pass_rate_hypothesis = ">=80%"
predicted_cheapest_correct_row = "frontier-low if floor rows duplicate or over-update records"
demote_if = "mock API contract is harder to debug than the task behavior"
```

### Work Packet

A local mock ticket API starts with existing incidents, ownership data, and labels. A manifest describes desired ticket state for a service migration. The agent must:

- find existing tickets by normalized external key,
- update stale canonical tickets,
- create missing tickets,
- mark duplicate tickets against the lowest numeric canonical ticket,
- reopen or close the canonical ticket to match `desired_status`,
- avoid touching archived or unrelated tickets.

One endpoint returns a documented transient error on first call, then succeeds.

### Why T4

This measures delegated tool/API action rather than code editing. The correct behavior is stateful and idempotent. Weak rows should fail by duplicating tickets, missing existing state, or making unnecessary/destructive calls.

### Verifier Contract

Required checks:

- Final mock API state matches expected state.
- Existing tickets are updated, not duplicated.
- Unrelated tickets remain unchanged.
- Duplicate API-side tickets are marked once with `duplicate_of`.
- Archived duplicate tickets remain unchanged.
- `desired_status=open` reopens closed tickets and `desired_status=closed` closes open tickets.
- Deterministic transient error is retried correctly.
- Audit JSONL contains only the documented action schema.

Pass-to-pass checks:

- API can list, read, update, create, link, and close records before the agent run.
- Existing unrelated records remain readable and unchanged.

Overreach checks:

- Creating duplicate tickets for an existing incident fails.
- Deleting or closing unrelated tickets fails.
- Call count is diagnostic unless it causes duplicate or destructive state.

### Expected Weak-Row Failure

- Creates new tickets instead of searching first.
- Handles visible manifest rows but misses duplicates.
- Does not retry the transient error.
- Touches unrelated API records.

### Contamination Notes

Abstract shape only: deterministic manifest reconciliation against local API-side state. No issue
text, patch, tests, filenames, or domain data should be copied.

### Local Validation

The task exists under `tasks/ticket-state-reconcile`. The unmodified base fails the hidden verifier
for the intended reconciliation, retry, duplicate, and idempotency gaps. The reference solution
passed three clean verifier runs, an alternate solution passed the same verifier, and Pier oracle
passed through the Docker runner.

### Calibration Outcome

N=15 cheap-anchor calibration on `shallowswe-calibration-v0.1` produced anchor pass rates of
0.333, 0.400, and 0.667, with median 0.400. GPT-5.5 medium passed 5/5 as the top-gated row.
The task is retained as a large workflow candidate under the current taxonomy.

## First Authoring Recommendation

Author in this order:

1. `ticket-state-reconcile`: authored and retained because state reconciliation exposed real large
   workflow failures.
2. `status-terminal-parity`: authored and locally validated, but N=1 cheap-anchor sweep saturated.
3. `config-key-rollover`: authored as a cheap plumbing probe. Its first N=1 expanded-panel sweep
   saturated, so it needs redesign or calibration evidence before large-size admission.
4. `ledger-schema-upgrade`: authored as a large-signal candidate, but N=15 cheap-panel calibration
   put it below the large band. Anchor pass rates were 0.800, 0.867, and 0.933, with median 0.867,
   so the N=1 Gemini failure was not stable enough for large admission.

The current 36-task scaffold already includes smaller ticket/update workflow coverage.

## Questions For External Review

Ask reviewers to judge the cards against these questions:

1. Which card feels most like real delegated work?
2. Which card is too artificial, ambiguous, or close to DeepSWE long-horizon work?
3. Which verifier is most likely to overfit to a reference solution?
4. Which card best exposes a cost-efficiency crossover without requiring cleverness?
5. Should Invoke T4 wait until Invoke T2/T3 exists, or is the mock API pattern simple enough to build directly?

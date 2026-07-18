# Failed Trajectory Validity Review

This review asks a different question from the mechanical verifier sanity audit:

- Did the verifier check behavior that was not clearly requested?
- Did it depend on hard-coded schemas, file names, values, or hidden fixture behavior that the prompt did not specify?
- Did the model failure look like a real implementation miss under a fair task contract?

Snapshot reviewed: 53 failed trajectories across 18 unique failed tasks.

## Summary

- Clear verifier/prompt contract issues: 5 tasks
- Borderline strictness or underspecified schema: 2 tasks
- Looks like legitimate model miss: 11 tasks

The official-solution sanity audit still matters: all 18 reviewed tasks have a bundled primary solution that passes the verifier in Docker. That means these are not broken verifiers in the sense of being unsatisfiable. The issue is whether a model should reasonably infer the verifier contract from the prompt.

## Clear Verifier/Prompt Contract Issues

### `feature-branch-select-commits`

Verdict: verifier/prompt issue.

The prompt says to apply only `c1-bugfix` and `c3-test` into `repo/`, omit telemetry and experimental config, and ensure `repo/app.py` contains the bug fix. The verifier additionally requires `/app/selected_commits.txt`, but that file is not mentioned in the prompt.

The commit JSON payloads are metadata-only (`id`, `kind`, `file`) and do not contain patch contents. The verifier also expects retry behavior for `408`, `429`, and `503`; that behavior is not derivable from the visible prompt or commit metadata. The failed trajectory implemented a plausible retry boundary and added tests, but missed hidden behavior and hidden bookkeeping.

Recommended action: either put `selected_commits.txt` and exact retry semantics in the prompt, or change the verifier to check only the stated applied files.

### `release-branch-cherry-pick`

Verdict: verifier/prompt issue.

The prompt says: apply only `patches/9f1-release-note.json`, keep `branch.txt` as `release/1.4`, and record only `9f1-release-note`. The hidden verifier creates a fresh root with `branch.txt = release/2.0` and expects `patches/b7-release-note.json` to be applied and recorded.

That hidden test contradicts the literal prompt. A generalized "apply the release-note patch for the current branch" task may be valid, but that is not what the instruction says.

Recommended action: rewrite the prompt to state the general rule, or remove the hidden branch/patch variation.

### `audit-log-normalization`

Verdict: verifier/prompt issue.

The prompt says to write normalized audit rows, rejects, and a summary under `output/`, but does not specify exact artifact names or schemas. The verifier requires:

- `output/summary.json`
- `output/normalized.csv` with columns `timestamp,actor,action,result`
- `output/rejects.csv` with columns `line,reason`
- reject reason literal `malformed_line`

A failed trajectory produced reasonable artifacts (`normalized.csv`, `rejects.csv`, `summary.csv`) but failed because the verifier required `summary.json` and exact schema literals not present in the prompt.

Recommended action: add exact file names, columns, JSON shape, and reject reason literals to the prompt.

### `markdown-table-inventory`

Verdict: verifier/prompt issue.

The prompt names `output/inventory.csv` and `output/summary.json`, and says the summary totals active services by team. It does not define the exact JSON shape. The verifier expects `{"active_services": N, "teams": {...}}`.

A failed trajectory wrote a reasonable by-team summary JSON directly, which satisfies "summary totals active services by team" semantically but not the verifier's hidden schema.

Recommended action: add exact `summary.json` schema to the prompt.

### `subscription-summary-report`

Verdict: verifier/prompt issue.

The prompt names `output/summary.json` and `output/plan_counts.csv`, but does not specify exact summary keys. The verifier expects `active_accounts`, `churned_accounts`, and `mrr`.

A failed trajectory used semantically reasonable keys (`active_subscriptions`, `churned_subscriptions`, `total_mrr`) and got the visible fixture values right, but failed the hidden key names.

Recommended action: add exact `summary.json` keys and `plan_counts.csv` columns to the prompt.

## Borderline Strictness / Underspecified Detail

### `billing-revenue-rollup`

Verdict: borderline prompt issue.

The prompt says `summary.json` has keys `open_disputes` and `recognized_revenue`, but does not specify whether `open_disputes` is a count, amount, or list. The verifier expects a count. One failed trajectory set `open_disputes` to the open dispute amount (`10.0`) while otherwise producing the requested files and rollup shape.

Recommended action: clarify `open_disputes` is a count.

### `ticket-state-reconcile`

Verdict: borderline strictness.

The core task is well specified. The failures are around exact audit values for `external_key`, especially preserving manifest whitespace/casing on `retry` and `dedupe` rows. The prompt says to use the manifest spelling on the canonical ticket after reconciliation, and the audit rows include `external_key`, but it does not explicitly say every audit row must use manifest spelling rather than normalized or empty values.

Recommended action: add one sentence: "For every audit row for a manifest item, `external_key` must be exactly the manifest row's original `external_key` string."

## Looks Like Legitimate Model Miss

These failures appear covered by the prompt and verifier without obvious hidden-contract unfairness:

- `config-key-rollover`: prompt explicitly says update env fixtures and README to use `DISPATCH_VISIBILITY`; failure left `.env.nightly` on `DISPATCH_INCLUDE_CLOSED`.
- `customer-health-dashboard-screen`: prompt fully defines metrics, risk calculation, HTML contract, routes, selectors, and tests; failure was a metric/row calculation mismatch.
- `deployment-approval-reconcile`: prompt fully defines processing order, blockers, audit rows, idempotency, and state mutation constraints; failure was state/audit mismatch.
- `feature-entitlements-admin-screen`: prompt fully defines routes, selector behavior, entitlement calculation, HTML contracts, and regression test expectations; failure was metric/row mismatch.
- `incident-comms-pipeline`: prompt fully defines processing order, notification keys, call-log behavior, and idempotency; failure included extra mutation/call-log behavior on replay.
- `invoice-multi-source-merge`: prompt explicitly defines date normalization, source precedence, reject sorting, output schemas, and summary keys; failures were formatting/reject-precedence mistakes.
- `ledger-schema-upgrade`: prompt explicitly defines exact output files, schemas, ordering, reject reasons, and summary totals; failure was summary/totals mismatch.
- `release-train-reconcile`: prompt explicitly defines ordering, idempotency, changelog, tag, audit, and forbidden operations; failure was ordering/idempotency behavior.
- `renewal-risk-admin-screen`: prompt explicitly defines risk reasons including `stale_usage` and exact HTML fields; failure omitted `stale_usage`.
- `strip-sort-allowlist`: prompt is small and exact; failure was script runtime failure.
- `ticket-update-dont-duplicate`: prompt explicitly defines ticket count, exact call-log line, comment requirement, and priority update; failures were script runtime failures.

## Implication For Calibration

The ceiling/floor numbers should not be interpreted naively until task contract issues are either fixed or excluded. The clearest candidates to fix before using final sizing labels are:

1. `feature-branch-select-commits`
2. `release-branch-cherry-pick`
3. `audit-log-normalization`
4. `markdown-table-inventory`
5. `subscription-summary-report`
6. `billing-revenue-rollup` if we want zero schema ambiguity
7. `ticket-state-reconcile` if we want audit-field strictness to be fully explicit

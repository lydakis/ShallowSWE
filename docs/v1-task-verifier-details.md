# V1 Task Verifier Details

This document explains what each official v1 task asks an agent to do, how it is verified, why the
check is strict enough for local validation, and what kind of shortcut should fail.

Important limitation: if a solver can read the hidden verifier, any benchmark can be gamed. The
strictness below assumes the normal benchmark split: the task prompt and fixture are visible, while
the verifier assertions and hidden/generated cases are not used as training data or direct prompt
content.

## Code

### `invoice-cli-regression-test-fix`

Task: This is a code task. The fixture has an invoice CSV importer that counts duplicate
`invoice_id` rows as separate invoices. The intended fix is to keep the first row for each invoice
ID and ignore later duplicate rows, then add a visible regression test proving that behavior.

Verifier: The hidden verifier creates a temporary CSV with a duplicate invoice whose second row has
a much larger amount. It imports the file and requires the invoice IDs to be exactly
`INV-200, INV-201`, the total to be `17.50`, and the open amount to be `10.00`. It also runs the CLI
and checks the printed count and total. Finally, it runs the visible test suite on the fixed code,
then copies the app, restores the original duplicate-counting importer, and requires the visible
tests to fail.

Why strict: A solution must fix runtime behavior and must add a regression test that catches the
original bug. A fake test file with the right words no longer passes.

Shortcut that fails: Counting all rows, keeping the last duplicate, fixing only the CLI, or adding a
test that does not fail against the original duplicate-import bug.

### `settings-null-default`

Task: Fix a settings loader that crashes when an optional nested `notifications` object is missing.
Missing notification fields should default to disabled.

Verifier: It calls `load_settings` on a full config, a config with no `notifications`, and a partial
config with only `email`. It also invokes the CLI and parses the emitted JSON.

Why strict: It checks the library API and CLI surface, and it covers both missing object and missing
field cases.

Shortcut that fails: Returning a hardcoded config, handling only the visible file, or fixing the
function but leaving the CLI broken.

### `date-window-inclusive`

Task: Fix a date filter that incorrectly excludes events on the end date.

Verifier: It calls the filter directly for a multi-day range and a same-day range, then runs the CLI
and checks exact event IDs in order.

Why strict: The assertions cover the boundary that was broken, preserve start-date behavior, and
check the CLI path.

Shortcut that fails: Adding one day blindly in the CLI only, sorting differently, or including dates
after the requested end date.

### `retry-error-fallback`

Task: Make a retry row parser return a documented fallback for malformed numeric fields instead of
raising.

Verifier: It checks a valid row, a malformed row, and the CLI output for a CSV containing both valid
and invalid rows.

Why strict: It requires preserving normal parsing while adding fallback behavior for bad input.

Shortcut that fails: Returning fallback for every row, swallowing the job ID, or only handling one
bad column.

### `report-json-format`

Task: Add JSON output support to an account report CLI without breaking existing output formats.

Verifier: It checks the JSON serializer output, invokes the CLI with JSON output, confirms CSV still
contains the old row, and checks that help text advertises JSON.

Why strict: It covers serializer, CLI wiring, backwards compatibility, and discoverability.

Shortcut that fails: Printing JSON only from the CLI while leaving the serializer unsupported, or
breaking CSV/text output.

### `user-export-field-rename`

Task: Add a new `name` field to user export rows while preserving the old `display_name` alias.

Verifier: It calls the exporter on fixture users, checks the field order, checks that `name` and
`display_name` match, and parses CSV output.

Why strict: It enforces compatibility and the new schema at the API and CSV boundary.

Shortcut that fails: Replacing `display_name` instead of preserving it, putting fields in the wrong
order, or updating only one output format.

### `auth-token-expiry-regression`

Task: Fix token expiry handling where new tokens use milliseconds but older tokens use seconds.

Verifier: It evaluates future millisecond, past millisecond, future second, and past second values
against a fixed `now`.

Why strict: The check prevents a one-unit-only fix and avoids time-of-day flakiness.

Shortcut that fails: Dividing every timestamp by 1000, treating every timestamp as seconds, or using
current wall-clock time in a way that changes results.

### `split-notification-renderer`

Task: Split notification rendering into text and HTML modules while preserving the old renderer
imports.

Verifier: It requires `notifications/text.py` and `notifications/html.py`, imports the new and old
paths, and checks text and HTML output equality.

Why strict: The task is not just file movement. It requires compatibility imports and stable output.

Shortcut that fails: Creating empty modules, deleting old imports, or changing rendered strings.

### `status-terminal-parity`

Task: Add a new terminal fulfillment status, `return_to_sender`, consistently across import,
webhook, admin repair, reporting, help text, and rejection behavior.

Verifier: It checks status normalization and alias `rts`, terminal and success semantics, CSV import,
webhook update behavior, repair CLI behavior, report counts, help text, and rejection of an unknown
nearby status.

Why strict: The new status must work across every entry point, not just one helper.

Shortcut that fails: Adding the enum only, accepting unknown statuses loosely, or updating reports
without updating repair/webhook paths.

### `webhook-idempotency-parity`

Task: Make duplicate event IDs idempotent across import, webhook, and replay paths.

Verifier: It builds repeated event lists and checks totals and processed event IDs for all three
entry points.

Why strict: It forces a shared idempotency behavior instead of fixing only the path shown in the
fixture.

Shortcut that fails: Deduping import only, deduping by order ID instead of event ID, or allowing
replay to double count.

### `api-pagination-consistency`

Task: Implement page/per-page slicing consistently for catalog service and summary behavior.

Verifier: It checks page 2, page 3 with a short final page, and the default unpaginated summary.

Why strict: It covers normal pagination, edge pagination, and backward compatibility.

Shortcut that fails: One-based/off-by-one paging, requiring pagination when absent, or paginating
only the CLI layer.

### `cache-invalidates-on-settings-change`

Task: Fix a file-backed feature flag cache that returns stale values after the file changes.

Verifier: It writes temporary settings files, reads once, edits the same file, reads again, and
checks a separate file remains isolated.

Why strict: It checks actual cache invalidation rather than a static fixture.

Shortcut that fails: Disabling file isolation, caching forever by path, or returning the same object
without re-reading changed content.

## Artifact

### `env-flags-to-json`

Task: Convert `input/flags.env` into typed JSON.

Verifier: The task must provide `scripts/build_outputs.py`. The verifier runs it on the visible
fixture and on a fresh hidden `input/flags.env` file with different keys, booleans, integers,
floats, strings, comments, malformed lines, and empty values. It parses JSON and compares typed
values. The visible prompt specifies the parser contract: ignore comments, blank lines, malformed
lines, and empty assignments; parse booleans, integers, and decimals; preserve other values as
strings; and write sorted JSON keys.

Why strict: The solver cannot pass by writing only the visible `output/flags.json`; it must implement
the parser rule.

Shortcut that fails: Treating everything as strings, keeping empty assignments, ignoring hidden
keys, or hardcoding the visible output.

### `extract-error-fields`

Task: Flatten nested error JSON into a CSV with selected columns.

Verifier: `scripts/build_outputs.py` is rerun on visible and hidden `errors.json` inputs. It checks
CSV rows, column names, row order, nested fields, and blank request IDs when context is missing.

Why strict: It validates extraction behavior on a second unseen input shape.

Shortcut that fails: Hardcoded visible CSV, missing optional-field handling, or wrong column order.

### `strip-sort-allowlist`

Task: Normalize an allowlist by stripping comments, lowercasing, deduping, and sorting domains.

Verifier: The build script runs on visible and hidden allowlist files. The hidden case includes
mixed case, duplicates, comments, and blank lines.

Why strict: It checks the canonicalization algorithm rather than one output file.

Shortcut that fails: Case-sensitive dedupe, preserving comments, or retaining input order.

### `spec-to-release-checklist`

Task: Convert release markdown bullet items into checklist JSON.

Verifier: The build script runs on the visible release spec and a hidden hotfix spec. It checks item
IDs, owner, title, required flags, and document order. The prompt specifies deterministic sequential
IDs (`rel-1`, `rel-2`, ...), field derivation, and required/optional handling, so exact assertions
trace back to visible requirements instead of hidden conventions.

Why strict: It requires parsing the markdown pattern on fresh content.

Shortcut that fails: Hardcoding the three visible checklist rows or treating optional items as
required.

### `payout-reconcile`

Task: Join invoices, payments, refunds, and customers into payout and reject reports.

Verifier: The CLI is run into a temp output directory. The verifier compares exact payout rows,
reject rows, headers, sorting, refund subtraction, unknown-customer rejects, and unknown-invoice
payment rejects.

Why strict: It checks multi-source reconciliation behavior and error handling.

Shortcut that fails: Joining payments only, ignoring refunds, omitting rejects, or outputting rows
in unstable order.

### `access-log-to-incidents`

Task: Parse mixed access logs into incidents, rejects, and summary JSON.

Verifier: `scripts/build_outputs.py` runs on visible and hidden logs. It checks 500+ as high
severity, 429 as medium, non-incident 200 rows ignored, malformed-line rejects, sorted incidents,
and aggregate counts.

Why strict: It tests the rule set on a second log file.

Shortcut that fails: Hardcoded incident rows, classifying every non-200 as high, or dropping reject
records.

### `markdown-table-inventory`

Task: Convert a markdown service inventory table into CSV and summary JSON.

Verifier: The build script runs on visible and hidden markdown tables. It checks table parsing,
retired-row exclusion, sorting by team/service, and active-service counts by team.

Why strict: It requires a parser for the table structure and status filter.

Shortcut that fails: Copying the visible CSV, including retired services, or grouping incorrectly.

### `subscription-summary-report`

Task: Summarize subscriptions into active account count, churned count, MRR, and plan counts.

Verifier: The build script runs on visible and hidden CSVs. It checks active-only MRR, cancelled
churn, trial exclusion, and plan counts across active/cancelled non-trial rows.

Why strict: The hidden CSV uses different plans and statuses.

Shortcut that fails: Counting trials, adding cancelled MRR, or hardcoding visible plan names.

### `ledger-schema-upgrade`

Task: Upgrade mixed billing inputs into a v3 ledger package with rejects and summary totals.

Verifier: It checks output schemas, canonical ledger rows, reject headers and reasons, totals, and
summary consistency.

Why strict: It verifies a package of related artifacts, not a single file.

Shortcut that fails: Emitting only ledger rows, skipping rejects, using the old schema, or producing
incorrect totals.

### `support-metrics-package`

Task: Produce support metrics from tickets, agents, SLA targets, and escalations.

Verifier: The build script runs on visible and hidden multi-file inputs. It checks agent ticket
counts, SLA breach counts, breach rows, escalation count, and total tickets.

Why strict: It validates joins across several input files and a second unseen fixture.

Shortcut that fails: Hardcoding visible agent IDs, counting breaches without SLA targets, or ignoring
escalations.

### `billing-revenue-rollup`

Task: Build revenue rollups from invoices, credits, and disputes.

Verifier: The build script runs on visible and hidden billing inputs. It checks paid-invoice gross,
credits by invoice, net revenue by plan, open-dispute adjustments, and recognized revenue.

Why strict: The hidden case changes plans, invoice status, credits, and dispute outcomes.

Shortcut that fails: Counting void invoices, subtracting disputes from revenue, ignoring credits, or
hardcoding visible plan rows.

### `audit-log-normalization`

Task: Normalize pipe-delimited audit logs into canonical CSV, rejects, and summary JSON.

Verifier: The build script runs on visible and hidden audit logs. It checks action normalization to
snake case, sorted rows, malformed-line rejects, action counts, and row totals.

Why strict: It validates normalization rules on a different action phrase.

Shortcut that fails: Copying visible rows, lowercasing without snake-case normalization, or ignoring
rejects.

## Workflow

### `ticket-cut-from-bug-report`

Task: Read a bug report and create one local mock ticket.

Verifier: The task must provide `scripts/apply_task.py`. The verifier runs it on the visible
checkout report and on a hidden billing report. It checks exact ticket state and call log in both
cases. The prompt specifies the deterministic component, ID, title, label, priority, status, and
call-log conventions for the visible checkout path and the hidden billing/payout path, including the
exact ticket fields.

Why strict: It prevents a solution that only writes the visible checkout ticket.

Shortcut that fails: Creating duplicate tickets, omitting the call log, or hardcoding only checkout.

### `post-build-status`

Task: Read a build result and write one formatted local status update.

Verifier: `scripts/apply_task.py` runs on a visible failed unit build and a hidden successful
integration build. It checks context, commit, state, body, and call log. The prompt specifies the
exact status fields (`body`, `commit`, `context`, `state`), `ci/{suite}` context, success/failure
state rule, body templates, call-log line, and overwrite-to-one-output behavior, so exact string
checks are tied to visible requirements and self-testing does not create duplicate visible state.

Why strict: It checks both failure and success paths, and it avoids rewarding scripts that only work
from the visible initial state.

Shortcut that fails: Always posting failure, hardcoding the visible commit, or omitting failed test
names.

### `rename-helper-symbol`

Task: Rename `format_user_key` to `format_user_id` across imports and call sites.

Verifier: It imports the helper and app module, checks behavior on multiple names, confirms the old
helper is no longer exported, and checks the call site no longer references the old name.

Why strict: It checks runtime imports and API cleanup.

Shortcut that fails: Adding the new name but leaving call sites on the old helper, or keeping the old
public symbol.

### `move-module-fix-imports`

Task: Move slug helpers to `text_tools/slug.py`, update imports, and preserve old import
compatibility.

Verifier: It imports both new and old paths, calls both functions, calls the app function, and checks
the app imports the new module.

Why strict: It requires behavior, compatibility, and internal import migration.

Shortcut that fails: Moving the file without wrapper compatibility or keeping the app on the old
path.

### `config-flag-ignored`

Task: Fix a documented dispatch config flag that is ignored at runtime.

Verifier: It loads config from env files, checks planner behavior, invokes the CLI, verifies the
legacy alias still works, and checks archived orders remain skipped by default.

Why strict: It covers config parsing, runtime effect, CLI behavior, compatibility, and default
safety.

Shortcut that fails: Reading the new flag but not using it, dropping legacy alias support, or
including archived records by default.

### `ticket-update-dont-duplicate`

Task: Update an existing matching mock ticket instead of filing a duplicate.

Verifier: `scripts/apply_task.py` runs on the visible ticket ID and a hidden ticket ID. It checks the
ticket count, priority change, comment, and update-only call log.

Why strict: It prevents hardcoding the visible ticket ID and checks idempotent update behavior.

Shortcut that fails: Creating a new ticket, updating the wrong ID, or appending duplicate comments on
rerun.

### `release-branch-cherry-pick`

Task: Apply only the release-note patch from a set of patch fixtures.

Verifier: `scripts/apply_task.py` runs on visible and hidden branch fixtures. It checks branch text,
release notes content, selected commit record, and absence of the experimental patch output.

Why strict: The hidden patch ID and content differ, so the solution must select by rule.

Shortcut that fails: Applying all patches, hardcoding `9f1-release-note`, or appending the same note
twice on rerun.

### `dependency-api-rename`

Task: Adapt app code to a vendored API rename from `notify_user` to `send_message`.

Verifier: It imports `send_alert`, calls it, checks the returned payload, and asserts the adapter no
longer references `notify_user`.

Why strict: It validates runtime behavior against the new dependency API.

Shortcut that fails: Recreating a local fake `notify_user`, changing payload fields, or editing the
vendor package instead of the adapter.

### `config-key-rollover`

Task: Migrate a dispatch visibility config key across runtime, fixtures, CLI help, and docs.

Verifier: It checks docs and fixture text, default behavior, active/archived/all modes, legacy alias
compatibility, region and account filters, CLI output, and help text.

Why strict: It covers the full config surface and precedence behavior.

Shortcut that fails: Updating docs only, supporting only one visibility value, breaking filters, or
removing legacy behavior.

### `ticket-state-reconcile`

Task: Reconcile a desired ticket manifest against deterministic local ticket API state.

Verifier: It checks dedupe of duplicate external keys, retry and reopen/close actions, creation of
missing tickets, preservation of archived state, audit log schema, no deletes, and an idempotent
noop case.

Why strict: It tests state reconciliation, side-effect logging, and repeat-run behavior.

Shortcut that fails: Replacing the whole ticket file blindly, deleting records, ignoring duplicates,
or writing audit entries without real state changes.

### `merge-divergent-config-branches`

Task: Merge main, release, and feature config branch fixtures with deterministic conflict rules.

Verifier: `scripts/apply_task.py` runs on visible and hidden branch configs. It checks region from
release, feature flags from feature, max timeout conflict resolution, and merge report metadata.

Why strict: Hidden configs change all relevant values, so the merge rule must be implemented.

Shortcut that fails: Copying the visible merged config, taking timeout from the wrong branch, or
dropping feature flags.

### `feature-branch-select-commits`

Task: Apply only selected bugfix and test commits from a mixed commit stack.

Verifier: It checks selected commit IDs, absence of telemetry and experiment files, presence of the
test file, and imports `repo/app.py` to test retry behavior for 408, 429, 503, and 400.

Why strict: It verifies both selected side effects and behavior.

Shortcut that fails: Applying all commits, omitting the test file, or changing retry behavior too
broadly.

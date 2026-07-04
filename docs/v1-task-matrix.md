# ShallowSWE V1 Task Matrix

This is the concrete 36-task target for v1:

```text
3 categories x 3 sizes x 4 tasks = 36 tasks
```

Each row is now an authored benchmark task folder under `tasks/<task-id>/`.

## Status Legend

- `existing`: task folder exists.
- `proposed`: task slot is defined, but no task folder exists yet.
- `smoke`: harness-only task; not counted in the 36-task benchmark.

## Code

Code tasks change software behavior: bugs, tests, features, refactors, and API/CLI/UI behavior.

### Small

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `invoice-cli-regression-test-fix` | existing | regression-test-plus-fix | Add duplicate-invoice regression coverage and fix importer dedupe. | Behavior, CLI total, and meaningful test addition. |
| `settings-null-default` | existing | missing-null-guard | Fix settings loader crash when optional nested config is missing. | Missing-field behavior and existing config paths. |
| `date-window-inclusive` | existing | wrong-comparison | Fix CLI date filtering that excludes the end date. | Boundary cases and unchanged start-date behavior. |
| `retry-error-fallback` | existing | exception-handling | Return documented fallback when a local retry parser sees a malformed row. | Fallback behavior and non-malformed rows. |

### Medium

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `report-json-format` | existing | small-feature-wiring | Add JSON output to an existing account report CLI. | Serializer, CLI flag, help, and old output formats. |
| `user-export-field-rename` | existing | small-feature-wiring | Add a new export field while preserving an old alias. | CLI/API output, alias compatibility, schema. |
| `auth-token-expiry-regression` | existing | debug-misleading-symptom | Fix login failures caused by expiry units flowing through the wrong layer. | End-to-end auth behavior and unchanged token parsing. |
| `split-notification-renderer` | existing | split-module-preserve-api | Split notification rendering into text/html modules without changing imports. | Public imports, CLI rendering, tests. |

### Large

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `status-terminal-parity` | existing | status-parity | Add `return_to_sender` consistently across fulfillment status surfaces. | Import, webhook, repair CLI, reporting, help, rejections. |
| `webhook-idempotency-parity` | existing | parallel-fix | Apply the same idempotency fix across import, webhook, and replay paths. | Duplicate prevention across all entry points. |
| `api-pagination-consistency` | existing | implement-cross-surface-feature | Add pagination consistently to service, CLI, and report layers. | Page boundaries, defaults, and old command behavior. |
| `cache-invalidates-on-settings-change` | existing | regression-from-diff | Repair stale cache behavior after settings changes without broad refactor. | Cache invalidation and unrelated cache hits. |

## Artifact

Artifact tasks turn local inputs into fixed outputs: data files, reports, migrations, summaries, and
docs-to-structured-output.

### Small

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `env-flags-to-json` | existing | env-to-json | Convert a small env file into typed JSON. | Exact keys, boolean/number parsing, ignored comments. |
| `extract-error-fields` | existing | extract-fields | Extract selected fields from nested error JSON into CSV. | Missing optional fields and column order. |
| `strip-sort-allowlist` | existing | strip-and-sort | Normalize, dedupe, and sort an allowlist file. | Canonical rows, comments, duplicates. |
| `spec-to-release-checklist` | existing | doc-to-checklist | Turn a short release markdown spec into checklist JSON. | Required checklist fields and deterministic ordering. |

### Medium

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `payout-reconcile` | existing | multi-source-join-with-rejects | Join invoices, payments, refunds, and customers into payouts/rejects. | Exact reports, reject reasons, sorting. |
| `access-log-to-incidents` | existing | log-to-schema | Parse mixed access logs into incident rows plus rejects. | Malformed lines, severity rules, aggregate counts. |
| `markdown-table-inventory` | existing | markdown-table-restructure | Reshape a markdown inventory table into grouped CSV and summary JSON. | Table parsing, grouping, totals. |
| `subscription-summary-report` | existing | report-summarize-fixed | Summarize subscriptions into MRR, churn, and plan counts. | Aggregates, currency formatting, exclusions. |

### Large

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `ledger-schema-upgrade` | existing | schema-upgrade-pipeline | Convert mixed billing inputs into v3 ledger outputs. | Schemas, ledger rows, rejects, summary totals. |
| `support-metrics-package` | existing | report-from-many | Produce a support metrics package from tickets, SLAs, agents, and escalations. | Multi-file joins, summaries, rejects. |
| `billing-revenue-rollup` | existing | ledger-or-reconciliation-package | Build revenue rollups from invoices, credits, disputes, and plans. | Multi-output package and capped adjustments. |
| `audit-log-normalization` | existing | dirty-data-normalize-at-scale | Normalize audit log rows with enumerated edge cases. | Aggregate counts and sampled canonical rows. |

## Workflow

Workflow tasks operate on repo, tool, or system state: config chains, git operations, local mock APIs,
tickets, and idempotent reconciliation.

### Small

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `ticket-cut-from-bug-report` | existing | cut-ticket | Turn a short bug report into one local mock ticket. | Final ticket fields and no duplicate calls. |
| `post-build-status` | existing | post-status | Read a local result file and post a formatted status update. | API state, status body, missing-result behavior. |
| `rename-helper-symbol` | existing | rename-symbol | Rename one helper across imports and call sites. | Tests, imports, old name removal where required. |
| `move-module-fix-imports` | existing | move-file-fix-imports | Move a module to a package path and repair imports. | Public import compatibility and command behavior. |

### Medium

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `config-flag-ignored` | existing | config-chain | Fix documented dispatch config flag ignored at runtime. | Config load, CLI behavior, alias compatibility. |
| `ticket-update-dont-duplicate` | existing | update-dont-duplicate | Find an existing ticket and update it instead of filing another one. | Final API state, idempotency, call log. |
| `release-branch-cherry-pick` | existing | branch-cherry-pick | Cherry-pick a release note fix onto a branch and resolve a trivial conflict. | Branch state, file content, tests. |
| `dependency-api-rename` | existing | dependency-bump-fix | Adapt one dependency API rename in an offline fixture package. | New API use and old behavior preservation. |

### Large

| Task ID | Status | Shape | Work Packet | Verifier Focus |
| --- | --- | --- | --- | --- |
| `config-key-rollover` | existing | cross-cutting-rename | Migrate a dispatch visibility config key with compatibility behavior. | Runtime, fixtures, docs, help, precedence. |
| `ticket-state-reconcile` | existing | reconcile-states | Reconcile desired ticket manifest against local API state. | Dedupe, retry, preservation, audit log. |
| `merge-divergent-config-branches` | existing | merge-divergent-branches | Merge a small config branch and resolve deterministic conflicts. | Branch state, resolved files, tests. |
| `feature-branch-select-commits` | existing | feature-branch-workflow | Select two of four commits by criteria and leave repo on target branch. | Branch fixture state, selected behavior, omitted behavior. |

## Cheap Local Check

Before any model run, each task should satisfy the local verifier shape: the untouched base fixture
fails, and the reference solution passes.

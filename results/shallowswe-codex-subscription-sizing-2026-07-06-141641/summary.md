# Codex Subscription Sizing

Tasks: 47

## Fixed Ceiling

- Model config: `openai/gpt-5.5[medium]`
- Passed: 39
- Failed: 8
- Pending: 0

## Diagnostic Effort Ladder

- High/xhigh are diagnostic rescue runs for medium failures only.
- Rescued by `high`: 2
- Rescued by `xhigh`: 0
- Not rescued or not run: 45

## Provisional Floor Sizes

- `small`: 30
- `medium`: 10
- `large`: 7
- `None`: 0

## Tasks

| Task | Metadata | Floor Probe | 5.5 Medium Ceiling | Diagnostic Rescue |
| --- | --- | --- | --- | --- |
| `access-log-to-incidents` | medium | small (3/3) | 1/1 | None |
| `api-pagination-consistency` | large | small (3/3) | 1/1 | None |
| `audit-log-normalization` | large | large (0/3) | 0/1 | None |
| `auth-token-expiry-regression` | medium | small (3/3) | 1/1 | None |
| `billing-revenue-rollup` | large | medium (2/3) | 1/1 | None |
| `cache-invalidates-on-settings-change` | large | small (3/3) | 1/1 | None |
| `config-flag-ignored` | medium | small (3/3) | 1/1 | None |
| `config-key-rollover` | large | medium (2/3) | 1/1 | None |
| `customer-health-dashboard-screen` | large | medium (2/3) | 0/1 | high |
| `date-window-inclusive` | small | small (3/3) | 1/1 | None |
| `dependency-api-rename` | medium | small (3/3) | 1/1 | None |
| `deployment-approval-reconcile` | large | small (3/3) | 0/1 | high |
| `dispatch-planner-split-parity` | large | small (3/3) | 1/1 | None |
| `env-flags-to-json` | small | small (3/3) | 1/1 | None |
| `extract-error-fields` | small | small (3/3) | 1/1 | None |
| `feature-branch-select-commits` | large | large (0/3) | 0/1 | None |
| `feature-entitlements-admin-screen` | large | medium (2/3) | 1/1 | None |
| `incident-comms-pipeline` | large | medium (1/3) | 0/1 | None |
| `invoice-cli-regression-test-fix` | small | small (3/3) | 1/1 | None |
| `invoice-multi-source-merge` | large | medium (1/3) | 1/1 | None |
| `ledger-restatement-audit` | large | small (3/3) | 1/1 | None |
| `ledger-schema-upgrade` | large | medium (2/3) | 1/1 | None |
| `markdown-table-inventory` | medium | large (0/3) | 0/1 | None |
| `merge-divergent-config-branches` | large | small (3/3) | 1/1 | None |
| `move-module-fix-imports` | small | small (3/3) | 1/1 | None |
| `payout-reconcile` | medium | small (3/3) | 1/1 | None |
| `post-build-status` | small | small (3/3) | 1/1 | None |
| `py-normalize-username` | small | small (3/3) | 1/1 | None |
| `release-branch-cherry-pick` | medium | large (0/3) | 0/1 | None |
| `release-train-reconcile` | large | medium (2/3) | 1/1 | None |
| `rename-helper-symbol` | small | small (3/3) | 1/1 | None |
| `renewal-risk-admin-screen` | large | medium (2/3) | 1/1 | None |
| `report-json-format` | medium | small (3/3) | 1/1 | None |
| `retry-error-fallback` | small | small (3/3) | 1/1 | None |
| `settings-null-default` | small | small (3/3) | 1/1 | None |
| `spec-to-release-checklist` | small | small (3/3) | 1/1 | None |
| `split-notification-renderer` | medium | small (3/3) | 1/1 | None |
| `status-terminal-parity` | large | small (3/3) | 1/1 | None |
| `strip-sort-allowlist` | small | medium (2/3) | 1/1 | None |
| `subscription-summary-report` | medium | large (0/3) | 0/1 | None |
| `support-metrics-package` | large | small (3/3) | 1/1 | None |
| `support-sla-business-hours` | large | small (3/3) | 1/1 | None |
| `ticket-cut-from-bug-report` | small | small (3/3) | 1/1 | None |
| `ticket-state-reconcile` | large | large (0/3) | 1/1 | None |
| `ticket-update-dont-duplicate` | medium | large (0/3) | 1/1 | None |
| `user-export-field-rename` | medium | small (3/3) | 1/1 | None |
| `webhook-idempotency-parity` | large | small (3/3) | 1/1 | None |

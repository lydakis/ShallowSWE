# Codex Subscription Calibration 2026-07-06

Tasks calibrated: 47

Band assignments in this document are provisional N=3 floor-probe labels, not statistically final task sizes.
The GPT-5.5 row in this document is Medium smoke evidence only; it is not the formal
Extra High ceiling gate.

## Summary

- Assigned size counts: large=7, medium=10, small=30
- Failed trajectories audited: 53
- Failed tasks: 18
- Contract issue tasks: 7

## Statistical Status

- Current floor bands are N=3 provisional labels.
- With N=3, the only observable pass rates are `0/3`, `1/3`, `2/3`, and `3/3`.
- The current provisional rule maps `0/3` to large, `1/3` or `2/3` to medium, and `3/3` to small.
- N=3 is useful for smoke testing and prioritization, not statistically significant banding.
- Use N=10 as the minimum useful confirmation pass.
- Use N=16 to N=20 for a final calibrated snapshot, especially near the 0.30 and 0.70 band boundaries.
- A statistically confirmed band should not have its uncertainty interval crossing a band boundary.

## Task Contract Review Counts

- `borderline_prompt_issue`: 1
- `borderline_strictness`: 1
- `legitimate_model_miss`: 11
- `no_failed_trajectory`: 29
- `verifier_prompt_contract_issue`: 5

## Tasks

| Task | Category | Previous Size | Provisional Size | Floor | Medium Smoke | Contract Review | Failed Trajectories |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| `access-log-to-incidents` | artifact | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `api-pagination-consistency` | code | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `audit-log-normalization` | artifact | large | large | 0/3 | 0/1 | `verifier_prompt_contract_issue` | 6 |
| `auth-token-expiry-regression` | code | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `billing-revenue-rollup` | artifact | large | medium | 2/3 | 1/1 | `borderline_prompt_issue` | 1 |
| `cache-invalidates-on-settings-change` | code | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `config-flag-ignored` | workflow | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `config-key-rollover` | workflow | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `customer-health-dashboard-screen` | code | large | medium | 2/3 | 0/1 | `legitimate_model_miss` | 2 |
| `date-window-inclusive` | code | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `dependency-api-rename` | workflow | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `deployment-approval-reconcile` | workflow | large | small | 3/3 | 0/1 | `legitimate_model_miss` | 1 |
| `dispatch-planner-split-parity` | code | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `env-flags-to-json` | artifact | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `extract-error-fields` | artifact | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `feature-branch-select-commits` | workflow | large | large | 0/3 | 0/1 | `verifier_prompt_contract_issue` | 6 |
| `feature-entitlements-admin-screen` | code | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `incident-comms-pipeline` | workflow | large | medium | 1/3 | 0/1 | `legitimate_model_miss` | 5 |
| `invoice-cli-regression-test-fix` | code | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `invoice-multi-source-merge` | code | large | medium | 1/3 | 1/1 | `legitimate_model_miss` | 2 |
| `ledger-restatement-audit` | artifact | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `ledger-schema-upgrade` | artifact | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `markdown-table-inventory` | artifact | medium | large | 0/3 | 0/1 | `verifier_prompt_contract_issue` | 6 |
| `merge-divergent-config-branches` | workflow | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `move-module-fix-imports` | workflow | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `payout-reconcile` | artifact | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `post-build-status` | workflow | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `py-normalize-username` | code | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `release-branch-cherry-pick` | workflow | medium | large | 0/3 | 0/1 | `verifier_prompt_contract_issue` | 6 |
| `release-train-reconcile` | workflow | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `rename-helper-symbol` | workflow | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `renewal-risk-admin-screen` | code | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `report-json-format` | code | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `retry-error-fallback` | code | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `settings-null-default` | code | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `spec-to-release-checklist` | artifact | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `split-notification-renderer` | code | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `status-terminal-parity` | code | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `strip-sort-allowlist` | artifact | small | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `subscription-summary-report` | artifact | medium | large | 0/3 | 0/1 | `verifier_prompt_contract_issue` | 6 |
| `support-metrics-package` | artifact | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `support-sla-business-hours` | artifact | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `ticket-cut-from-bug-report` | workflow | small | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `ticket-state-reconcile` | workflow | large | large | 0/3 | 1/1 | `borderline_strictness` | 3 |
| `ticket-update-dont-duplicate` | workflow | medium | large | 0/3 | 1/1 | `legitimate_model_miss` | 3 |
| `user-export-field-rename` | code | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `webhook-idempotency-parity` | code | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |

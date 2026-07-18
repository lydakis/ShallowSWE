# Codex Subscription Sizing

Tasks: 11

## Formal Ceiling

- Model config: `openai/gpt-5.5[extra_high]`
- Medium smoke rows, when present, are not formal ceiling evidence.
- Passed: 9
- Failed: 2
- Excluded: 0
- Pending: 0

## Provisional Floor Sizes

- `small`: 3
- `medium`: 0
- `large`: 8
- `None`: 0

## Tasks

| Task | Metadata | Floor Probe | Formal Ceiling | Medium Smoke |
| --- | --- | --- | --- | --- |
| `billing-revenue-rollup` | large | large (0/1) | 1/1 | pending |
| `config-key-rollover` | large | large (0/1) | 0/1 | pending |
| `customer-health-dashboard-screen` | large | large (0/1) | 1/1 | pending |
| `feature-entitlements-admin-screen` | large | large (0/1) | 1/1 | pending |
| `incident-comms-pipeline` | large | large (0/1) | 0/1 | pending |
| `invoice-multi-source-merge` | large | large (0/1) | 1/1 | pending |
| `ledger-schema-upgrade` | large | small (1/1) | 1/1 | pending |
| `release-train-reconcile` | large | large (0/1) | 1/1 | pending |
| `renewal-risk-admin-screen` | large | small (1/1) | 1/1 | pending |
| `status-fanout-reconcile` | medium | small (1/1) | 1/1 | pending |
| `ticket-update-dont-duplicate` | medium | large (0/1) | 1/1 | pending |

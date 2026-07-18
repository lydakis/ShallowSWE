# Codex Subscription Sizing

Tasks: 7

## Fixed Ceiling

- Model config: `openai/gpt-5.5[medium]`
- Passed: 7
- Failed: 0
- Excluded: 0
- Pending: 0

## Diagnostic Effort Ladder

- High/xhigh are diagnostic rescue runs for medium failures only.
- Rescued by `high`: 0
- Rescued by `xhigh`: 0
- Not rescued or not run: 7

## Provisional Floor Sizes

- `small`: 4
- `medium`: 3
- `large`: 0
- `None`: 0

## Tasks

| Task | Metadata | Floor Probe | 5.5 Medium Ceiling | Diagnostic Rescue |
| --- | --- | --- | --- | --- |
| `audit-log-normalization` | large | medium (2/3) | 1/1 | None |
| `billing-revenue-rollup` | large | medium (2/3) | 1/1 | None |
| `feature-branch-select-commits` | large | medium (2/3) | 1/1 | None |
| `markdown-table-inventory` | medium | small (3/3) | 1/1 | None |
| `release-branch-cherry-pick` | medium | small (3/3) | 1/1 | None |
| `subscription-summary-report` | medium | small (3/3) | 1/1 | None |
| `ticket-state-reconcile` | large | small (3/3) | 1/1 | None |

# Codex Subscription Calibration 2026-07-06

Tasks calibrated: 7

Band assignments in this document are provisional N=3 floor-probe labels, not statistically final task sizes.
The GPT-5.5 row in this document is Medium smoke evidence only; it is not the formal
Extra High ceiling gate.

## Summary

- Assigned size counts: medium=3, small=4
- Failed trajectories audited: 3
- Failed tasks: 3
- Contract issue tasks: 0

## Statistical Status

- Current floor bands are N=3 provisional labels.
- With N=3, the only observable pass rates are `0/3`, `1/3`, `2/3`, and `3/3`.
- The current provisional rule maps `0/3` to large, `1/3` or `2/3` to medium, and `3/3` to small.
- N=3 is useful for smoke testing and prioritization, not statistically significant banding.
- Use N=10 as the minimum useful confirmation pass.
- Use N=16 to N=20 for a final calibrated snapshot, especially near the 0.30 and 0.70 band boundaries.
- A statistically confirmed band should not have its uncertainty interval crossing a band boundary.

## Task Contract Review Counts

- `legitimate_model_miss`: 3
- `no_failed_trajectory`: 4

## Tasks

| Task | Category | Previous Size | Provisional Size | Floor | Medium Smoke | Contract Review | Failed Trajectories |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| `audit-log-normalization` | artifact | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `billing-revenue-rollup` | artifact | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `feature-branch-select-commits` | workflow | large | medium | 2/3 | 1/1 | `legitimate_model_miss` | 1 |
| `markdown-table-inventory` | artifact | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `release-branch-cherry-pick` | workflow | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `subscription-summary-report` | artifact | medium | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |
| `ticket-state-reconcile` | workflow | large | small | 3/3 | 1/1 | `no_failed_trajectory` | 0 |

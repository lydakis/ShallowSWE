# Codex Subscription Sizing

Tasks: 6

## Fixed Ceiling

- Model config: `openai/gpt-5.5[medium]`
- Passed: 6
- Failed: 0
- Excluded: 0
- Pending: 0

## Diagnostic Effort Ladder

- High/xhigh are diagnostic rescue runs for medium failures only.
- Rescued by `high`: 0
- Rescued by `xhigh`: 0
- Not rescued or not run: 6

## Provisional Floor Sizes

- `small`: 5
- `medium`: 1
- `large`: 0
- `None`: 0

## Tasks

| Task | Metadata | Floor Probe | 5.5 Medium Ceiling | Diagnostic Rescue |
| --- | --- | --- | --- | --- |
| `access-log-sessionize` | medium | small (3/3) | 1/1 | None |
| `billing-proration-schedule` | medium | small (3/3) | 1/1 | None |
| `notification-locale-fallback` | medium | small (3/3) | 1/1 | None |
| `retry-policy-migration` | medium | small (3/3) | 1/1 | None |
| `status-fanout-reconcile` | medium | medium (1/3) | 1/1 | None |
| `ticket-bulk-triage` | medium | small (3/3) | 1/1 | None |

# Customer Health Dashboard Screen

You are working in a Python static web-rendering app. The existing app renders routes through:

```bash
python -m workspace_app.cli --route /accounts --data-dir fixtures/visible --output /tmp/out.html
```

Add a new `/customer-health` screen that integrates with the existing app instead of creating a separate script.

## Required product behavior

- Register route `/customer-health`.
- Add a primary navigation item with label `Customer Health` and href `/customer-health`.
- Add `workspace_app/screens/customer_health.py`.
- Add `workspace_app/selectors/customer_health.py`.
- Preserve the existing routes `/`, `/accounts`, `/support`, `/billing`, and `/reports`.
- Add a regression test under `tests/` that is discovered by `python -m unittest discover -s tests`.

The new route reads the same `--data-dir` used by the CLI. The data directory contains:

- `accounts.json`: list of accounts with `account_id`, `name`, `owner`, and `plan`.
- `tickets.json`: list of tickets with `account_id` and `status`; only `status == "open"` counts as open.
- `incidents.json`: list of incidents with `account_id`, `status`, and `severity`; for this task, `open_incident_count` means the count of incidents where `status == "open"` and `severity` is `major` or `critical`. Ignore open `minor` incidents and resolved incidents for both `open_incident_count` and risk.
- `usage.json`: list of usage records with `account_id`, `previous_period_events`, and `current_period_events`.
- `renewals.json`: object with `report_date` and `renewals`, where each renewal has `account_id` and `renewal_date`.

## Risk calculation

For every account, compute `days_until_renewal` as `renewal_date - report_date` in whole days. Compute `risk_score`:

- start at `0`
- add `40` if `days_until_renewal <= 30`
- add `25` if `open_incident_count >= 1`
- add `min(30, open_ticket_count * 6)`
- add `20` if usage is down, meaning `current_period_events < previous_period_events`
- subtract `10` if `plan == "enterprise"` and usage is up, meaning `current_period_events > previous_period_events`
- clamp the final score to the range `0..100`

Compute `risk_band` from the final score:

- `high` when score is at least `70`
- `medium` when score is at least `40`
- `low` otherwise

Compute `recommended_action` with this priority order:

1. If the account has an open `major` or `critical` incident: `Escalate incident response`
2. Else if `days_until_renewal <= 30` and the risk band is `high`: `Schedule renewal save plan`
3. Else if `open_ticket_count >= 4`: `Clear support queue`
4. Else if usage is down: `Review adoption drop`
5. Else: `Monitor`

Sort account rows by:

1. `risk_score` descending
2. `days_until_renewal` ascending
3. account `name` ascending

## Required HTML contract

The rendered page must include:

- `<main data-screen="customer-health">`
- an `<h1>` whose text is exactly `Customer Health`
- metrics with `data-metric` keys:
  - `accounts`
  - `high-risk`
  - `open-tickets`
  - `renewals-30d`
- a table with `data-table="customer-health-risks"`
- one table row per account with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `name`
  - `owner`
  - `plan`
  - `risk_score`
  - `risk_band`
  - `open_ticket_count`
  - `open_incident_count` using the open `major`/`critical` incident count defined above
  - `days_until_renewal`
  - `recommended_action`

Metric values should be plain numeric text. `renewals-30d` counts accounts whose renewal delta is from `0` through `30` days inclusive.

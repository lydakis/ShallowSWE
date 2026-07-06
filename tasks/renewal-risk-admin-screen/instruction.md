# Renewal Risk Admin Screen

You are working in a Python static web-rendering app. The existing app renders routes through:

```bash
python -m workspace_app.cli --route /accounts --data-dir fixtures/visible --output /tmp/out.html
```

Add a new renewal operations admin area that integrates with the existing app instead of creating a separate script.

## Required Product Behavior

- Register route `/renewals/risk`.
- Register route `/renewals/concessions`.
- Add a primary navigation item with label `Renewals` and href `/renewals/risk`.
- Add `workspace_app/screens/renewal_risk.py`.
- Add `workspace_app/screens/renewal_concessions.py`.
- Add `workspace_app/selectors/renewals.py`.
- Preserve the existing routes `/`, `/accounts`, `/support`, `/billing`, and `/reports`.
- Add a regression test under `tests/` that is discovered by `python -m unittest discover -s tests` and exercises both `/renewals/risk` and `/renewals/concessions`.

The new routes read the same `--data-dir` used by the CLI. The data directory contains:

- `accounts.json`: list of accounts with `account_id`, `name`, `owner`, and `segment`.
- `contracts.json`: object with `report_date` and `contracts`; each contract has `account_id`, `status`, `renewal_date`, and `arr`.
- `usage.json`: list of usage records with `account_id`, `active_users`, `licensed_seats`, and `last_login_at`.
- `tickets.json`: list of support tickets with `account_id`, `severity`, `status`, and `opened_at`.
- `concessions.json`: list of commercial concessions with `account_id`, `type`, `amount`, `expires_on`, and `reason`.

Render one renewal-risk row for every account. A concession is active only when `expires_on >= report_date`. Expired concessions must be ignored for active-concession calculations. If multiple active concessions exist for the same account, use the one with the latest `expires_on` on the risk screen.

## Renewal Risk Calculation

For each account row:

- `days_to_renewal` is `renewal_date - report_date` in whole days.
- `seat_utilization_pct` is the integer floor of `active_users * 100 / licensed_seats`; use `0` when `licensed_seats` is `0`.
- `open_critical_tickets` counts tickets for the account where `severity` is `critical` and `status` is not `closed` or `resolved`.
- `concession_days_remaining` is `expires_on - report_date` in whole days for the account's latest active concession; otherwise it is blank.
- A contract is active only when its `status` is `active` or `trialing`.
- `stale_usage` is true when `last_login_at` is more than 30 days before `report_date`.

Compute `risk_level` with this priority order:

1. `blocked` if the contract is not active.
2. `critical` if `open_critical_tickets >= 1`.
3. `critical` if `days_to_renewal <= 14` and `seat_utilization_pct < 50`.
4. `attention` if `days_to_renewal <= 30`.
5. `attention` if `seat_utilization_pct < 60`.
6. `attention` if an active concession exists and `concession_days_remaining <= 14`.
7. `attention` if `arr >= 100000` and `stale_usage` is true.
8. `healthy` otherwise.

Compute `recommended_action` with the same priority:

1. Inactive contract: `Restore contract`
2. Open critical ticket: `Escalate support`
3. Renewal within 14 days with low utilization: `Executive renewal review`
4. Renewal within 30 days: `Schedule renewal plan`
5. Low utilization: `Drive adoption plan`
6. Active concession expiring within 14 days: `Review concession`
7. High ARR with stale usage: `Verify executive engagement`
8. Otherwise: `Monitor`

Compute `risk_reasons` as a comma-separated list in this exact order, or `none` when empty. Join multiple codes with a literal comma and no spaces.

1. `contract_not_active` when the contract is not active
2. `renewal_soon` when `days_to_renewal <= 30`
3. `low_seat_utilization` when `seat_utilization_pct < 60`
4. `open_critical_ticket` when `open_critical_tickets >= 1`
5. `concession_expiring` when an active concession expires within 14 days
6. `stale_usage` when `arr >= 100000` and `stale_usage` is true

Sort risk rows by:

1. risk severity: `blocked`, then `critical`, then `attention`, then `healthy`
2. owner ascending
3. account name ascending

## Required Risk HTML Contract

The `/renewals/risk` route must include:

- `<main data-screen="renewal-risk">`
- an `<h1>` whose text is exactly `Renewal Risk`
- metrics with `data-metric` keys:
  - `accounts`
  - `critical`
  - `attention`
  - `concessions-expiring`
- a table with `data-table="renewal-risk"`
- one table row per account with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `account`
  - `owner`
  - `segment`
  - `arr`
  - `days_to_renewal`
  - `seat_utilization_pct`
  - `open_critical_tickets`
  - `concession_days_remaining`
  - `risk_level`
  - `risk_reasons`
  - `recommended_action`

Metric values should be plain numeric text. The element that has a `data-metric` attribute should have text content equal to the numeric value only.

Metric definitions:

- `accounts`: number of accounts.
- `critical`: number of rows whose `risk_level` is `blocked` or `critical`.
- `attention`: number of rows whose `risk_level` is `attention`.
- `concessions-expiring`: number of risk rows with an active concession expiring within 14 days.

## Required Concession Review Screen

The `/renewals/concessions` route must include:

- `<main data-screen="renewal-concessions">`
- an `<h1>` whose text is exactly `Renewal Concessions`
- metrics with `data-metric` keys:
  - `active-concessions`
  - `expiring-concessions`
  - `total-concession-amount`
- a table with `data-table="renewal-concessions"`
- one row per active concession after applying the latest-`expires_on` rule for duplicate account concessions, with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `account`
  - `owner`
  - `type`
  - `amount`
  - `days_remaining`
  - `status`
  - `reason`

Sort active concession rows by `days_remaining` ascending, then owner ascending, then account name ascending, then type ascending. Concession row `status` is `expiring` when `days_remaining <= 14`, otherwise `active`. `total-concession-amount` is the sum of active concession `amount` values after duplicate collapsing.

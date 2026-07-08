# Customer Health Command Center

You are working in a Python static web-rendering app. The existing app renders routes through:

```bash
python -m workspace_app.cli --route /accounts --data-dir fixtures/visible --output /tmp/out.html
```

Implement a multi-page customer health feature inside the existing app. Integrate with the
current routing, navigation, layout, selectors, and test structure instead of creating a
separate script.

## Required Product Behavior

- Register these routes:
  - `/customer-health`
  - `/customer-health/actions`
  - `/customer-health/owner-queue`
  - `/customer-health/recovery-plan`
- Add a primary navigation item with label `Customer Health` and href `/customer-health`.
- Add these screen modules:
  - `workspace_app/screens/customer_health.py`
  - `workspace_app/screens/customer_health_actions.py`
  - `workspace_app/screens/customer_health_owner_queue.py`
  - `workspace_app/screens/customer_health_recovery_plan.py`
- Add `workspace_app/selectors/customer_health.py`.
- Preserve the existing routes `/`, `/accounts`, `/support`, `/billing`, and `/reports`.
- Add a regression test under `tests/` that is discovered by
  `python -m unittest discover -s tests` and exercises all four new routes plus the export path.
- Extend `workspace_app.cli` with:

  ```bash
  python -m workspace_app.cli --data-dir fixtures/visible --export-customer-health /tmp/customer-health.json
  ```

  This command writes the JSON export described below. It must not render HTML when the export flag
  is used, and it must still preserve the existing route rendering behavior.

All four routes must read the same `--data-dir` used by the CLI. The data directory contains:

- `accounts.json`: list of accounts with `account_id`, `name`, `owner`, and `plan`.
- `tickets.json`: list of tickets with `account_id` and `status`; only `status == "open"`
  counts as open.
- `incidents.json`: list of incidents with `account_id`, `status`, and `severity`; for this
  task, `open_incident_count` means the count of incidents where `status == "open"` and
  `severity` is `major` or `critical`. Ignore open `minor` incidents and resolved incidents
  for both `open_incident_count` and risk.
- `usage.json`: list of usage records with `account_id`, `previous_period_events`, and
  `current_period_events`.
- `renewals.json`: object with `report_date` and `renewals`, where each renewal has
  `account_id` and `renewal_date`.
- `contracts.json`: object with `contracts`; each contract has `account_id`, `status`, and
  `arr`. A contract is active when `status` is `active` or `trialing`.
- `engagements.json`: list of engagement records with `account_id`, `last_touch_at`,
  `next_touch_at`, `channel`, and `status`. Use the latest record by `last_touch_at` when an
  account has more than one engagement.
- `playbooks.json`: list of customer plan records with `account_id`, `playbook`, `owner`,
  `due_date`, `status`, and `blockers`. A playbook is open when `status != "done"`. An open
  playbook is overdue when `due_date <= report_date`.

## Shared Customer Health Model

For every account, compute `days_until_renewal` as `renewal_date - report_date` in whole days.
Compute `engagement_gap` as `yes` when either:

- the latest `last_touch_at` is more than 45 days before `report_date`, or
- the latest `next_touch_at` is before `report_date`

Otherwise `engagement_gap` is `no`. If no engagement exists for the account, treat it as
`yes`.

Compute `risk_score`:

- start at `0`
- add `40` if `days_until_renewal <= 30`
- add `25` if `open_incident_count >= 1`
- add `min(30, open_ticket_count * 6)`
- add `20` if usage is down, meaning `current_period_events < previous_period_events`
- subtract `10` if `plan == "enterprise"` and usage is up, meaning
  `current_period_events > previous_period_events`
- add `35` if the contract is not active
- add `20` if `overdue_playbooks >= 1`
- add `15` if `engagement_gap == "yes"`
- clamp the final score to the range `0..100`

Compute `risk_band` from the final score:

- `high` when score is at least `70`
- `medium` when score is at least `40`
- `low` otherwise

Compute `recommended_action` with this priority order:

1. If the contract is not active: `Restore contract`
2. Else if the account has an open `major` or `critical` incident:
   `Escalate incident response`
3. Else if `overdue_playbooks >= 1`: `Clear customer plan blockers`
4. Else if `days_until_renewal <= 30` and the risk band is `high`:
   `Schedule renewal save plan`
5. Else if `open_ticket_count >= 4`: `Clear support queue`
6. Else if `engagement_gap == "yes"`: `Re-engage account owner`
7. Else if usage is down: `Review adoption drop`
8. Else: `Monitor`

Compute `recovery_stage` with this priority order:

1. `contract_restore` when the contract is not active
2. `incident_response` when `open_incident_count >= 1`
3. `renewal_save` when `days_until_renewal <= 30` and `risk_band == "high"`
4. `playbook_cleanup` when `overdue_playbooks >= 1`
5. `engagement_restart` when `engagement_gap == "yes"`
6. `monitoring` otherwise

Compute `blocker_count` as `open_incident_count + overdue_playbooks`, plus `1` when the contract
is not active, plus `1` when `engagement_gap == "yes"`.

Compute `action_due` as `next_playbook_due` when present; otherwise `report_date` for
`contract_restore` or `incident_response`; otherwise `renewal_date` for `renewal_save`; otherwise
blank.

Compute `executive_touch_due` as `yes` when `arr >= 100000` and either `risk_band != "low"` or
`days_until_renewal <= 30`; otherwise `no`.

## `/customer-health` HTML Contract

Sort account rows by:

1. `risk_score` descending
2. `days_until_renewal` ascending
3. account `name` ascending

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
  - `open_incident_count`
  - `days_until_renewal`
  - `arr`
  - `contract_status`
  - `engagement_gap`
  - `open_playbooks`
  - `overdue_playbooks`
  - `next_playbook_due`
  - `recommended_action`

Metric values should expose a plain numeric value; labeled stat-card markup is acceptable if the
numeric value is the trailing text for the `data-metric` element. `renewals-30d` counts accounts
whose renewal delta is from `0` through `30` days inclusive.

## `/customer-health/actions` HTML Contract

Include one row per account where `recommended_action != "Monitor"` or `open_playbooks > 0`.
Sort rows by:

1. risk severity: `high`, then `medium`, then `low`
2. `overdue_playbooks` descending
3. `next_playbook_due` ascending, with blank dates last
4. account name ascending

The rendered page must include:

- `<main data-screen="customer-health-actions">`
- an `<h1>` whose text is exactly `Customer Health Actions`
- metrics with `data-metric` keys:
  - `actions`
  - `overdue-playbooks`
  - `engagement-gaps`
  - `arr-at-risk`
- a table with `data-table="customer-health-actions"`
- one table row per included account with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `account`
  - `owner`
  - `risk_band`
  - `recommended_action`
  - `next_playbook_due`
  - `overdue_playbooks`
  - `open_playbooks`
  - `arr`
  - `engagement_gap`

Metric values should expose a plain numeric value; labeled stat-card markup is acceptable if the
numeric value is the trailing text for the `data-metric` element. `arr-at-risk` is the sum of ARR
for action rows whose `risk_band` is not `low`.

## `/customer-health/owner-queue` HTML Contract

Aggregate account rows by account owner. Sort owner rows by:

1. `escalation_needed == "yes"` before `no`
2. `arr_at_risk` descending
3. owner ascending

The rendered page must include:

- `<main data-screen="customer-health-owner-queue">`
- an `<h1>` whose text is exactly `Customer Health Owner Queue`
- metrics with `data-metric` keys:
  - `owners`
  - `owners-with-escalations`
  - `overdue-playbooks`
  - `arr-at-risk`
- a table with `data-table="customer-health-owner-queue"`
- one table row per owner with `data-owner="<owner>"`
- cells in each row with `data-field` keys:
  - `owner`
  - `accounts`
  - `high_risk_accounts`
  - `open_tickets`
  - `open_incidents`
  - `overdue_playbooks`
  - `engagement_gaps`
  - `arr_at_risk`
  - `next_playbook_due`
  - `escalation_needed`

For owner rows:

- `arr_at_risk` is the sum of ARR for owned accounts whose `risk_band` is not `low`.
- `escalation_needed` is `yes` when the owner has at least one high-risk account, at least two
  overdue playbooks, or at least one open major/critical incident; otherwise it is `no`.
- `next_playbook_due` is the earliest open playbook due date for that owner, or blank if none
  exists.

## `/customer-health/recovery-plan` HTML Contract

Include one row per account where `recovery_stage != "monitoring"` or `risk_band != "low"`. Sort
rows by:

1. recovery-stage severity: `contract_restore`, `incident_response`, `renewal_save`,
   `playbook_cleanup`, `engagement_restart`, `monitoring`
2. `blocker_count` descending
3. `action_due` ascending, with blank dates last
4. account name ascending

The rendered page must include:

- `<main data-screen="customer-health-recovery-plan">`
- an `<h1>` whose text is exactly `Customer Health Recovery Plan`
- metrics with `data-metric` keys:
  - `recovery-accounts`
  - `blocked-plans`
  - `exec-touches`
  - `arr-in-plan`
- a table with `data-table="customer-health-recovery-plan"`
- one table row per included account with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `account`
  - `owner`
  - `risk_band`
  - `recovery_stage`
  - `blocker_count`
  - `action_due`
  - `executive_touch_due`
  - `arr`
  - `recommended_action`

`blocked-plans` counts rows whose `recovery_stage` is `contract_restore` or `incident_response`.
`exec-touches` counts rows whose `executive_touch_due` is `yes`. `arr-in-plan` is the sum of ARR
for included rows.

## JSON Export Contract

`--export-customer-health` writes a deterministic JSON object with exactly these top-level keys:

- `report_date`
- `dashboard_rows`
- `action_rows`
- `owner_rows`
- `recovery_rows`
- `summary`

Rows must use the same ordering and field names as their matching HTML contracts, with
`account_id` included for account rows. `summary` must contain exactly:

- `accounts`
- `high_risk`
- `actions`
- `owners_with_escalations`
- `recovery_accounts`
- `arr_at_risk`
- `arr_in_recovery`

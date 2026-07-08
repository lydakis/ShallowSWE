# Build Seat Compliance Admin Console

You are working in a Python static web-rendering app. The existing app renders routes through:

```bash
python -m workspace_app.cli --route /accounts --data-dir fixtures/visible --output /tmp/out.html
```

Implement a multi-page seat compliance feature inside the existing app. Integrate with the current
routing, navigation, layout, selectors, and test structure instead of creating a separate script.

## Required Product Behavior

- Register these routes:
  - `/seat-compliance`
  - `/seat-compliance/overages`
  - `/seat-compliance/owner-queue`
  - `/seat-compliance/action-log`
- Add a primary navigation item with label `Seat Compliance` and href `/seat-compliance`.
- Add these screen modules:
  - `workspace_app/screens/seat_compliance.py`
  - `workspace_app/screens/seat_compliance_overages.py`
  - `workspace_app/screens/seat_compliance_owner_queue.py`
  - `workspace_app/screens/seat_compliance_action_log.py`
- Add `workspace_app/selectors/seat_compliance.py`.
- Preserve the existing routes `/`, `/accounts`, `/support`, `/billing`, and `/reports`.
- Add a regression test under `tests/` that is discovered by
  `python -m unittest discover -s tests` and exercises all four new routes.
- Extend `workspace_app.cli` with:

  ```bash
  python -m workspace_app.cli --data-dir fixtures/visible --export-seat-compliance /tmp/seat-review.json
  ```

  This command writes the JSON export described below. It must not render HTML when the export flag
  is used, and it must still preserve the existing route rendering behavior.

All three routes must read the same `--data-dir` used by the CLI. The data directory contains:

- `accounts.json`: list of accounts with `account_id`, `name`, `owner`, `plan`, `segment`, and
  `arr`.
- `subscriptions.json`: object with `report_date` and `subscriptions`; each subscription has
  `account_id`, `status`, and `renewal_date`.
- `plan_limits.json`: object keyed by plan. Each plan has `seat_limit`, `contractor_limit`, and
  `included_sso`.
- `allocations.json`: list of seat overrides with `account_id`, `seat_limit_override`,
  `effective_on`, and `source`.
- `users.json`: list of users with `account_id`, `status`, `user_type`, and `sso_enabled`.
- `invitations.json`: list of invitations with `account_id`, `status`, `expires_on`, and
  `user_type`.
- `exceptions.json`: list of temporary exceptions with `account_id`, `control`, `expires_on`,
  `reason`, and `approver`.
- `tickets.json`: list of support tickets with `account_id`, `status`, and `priority`.

## Shared Seat Compliance Model

For every account:

- `report_date` comes from `subscriptions.json`.
- A subscription is serviceable only when `status` is `active` or `trialing`.
- `renewal_days` is `renewal_date - report_date` in whole days.
- Use the latest allocation row whose `effective_on <= report_date` as the account's
  `seat_limit`. If no such allocation exists, use the plan's `seat_limit`.
- Count `active_users` where `status == "active"`.
- Count `active_contractors` where `status == "active"` and `user_type == "contractor"`.
- Count `pending_invites` where `status == "pending"` and `expires_on >= report_date`.
- Count `pending_contractor_invites` from the pending invites above where `user_type == "contractor"`.
- Count `expired_invites` where `status == "pending"` and `expires_on < report_date`.
- `billable_seats = active_users + pending_invites`.
- `contractor_seats = active_contractors + pending_contractor_invites`.
- `sso_gaps` is the number of active employee users with `sso_enabled == false`, but only when the
  plan has `included_sso == true`; otherwise it is `0`.
- Active exceptions have `expires_on >= report_date`.
- `exception_controls` is the ordered list of active exception controls that match raw reason codes
  and are not `subscription_not_serviceable` or `expired_invites`.
- `open_priority_tickets` counts tickets where `status == "open"` and `priority` is `p0` or `p1`.

Evaluate raw reason codes in this exact order:

1. `subscription_not_serviceable` when the subscription is not serviceable
2. `seat_overage` when `billable_seats > seat_limit`
3. `contractor_overage` when `contractor_seats > contractor_limit`
4. `sso_gap` when `sso_gaps > 0`
5. `expired_invites` when `expired_invites > 0`

Apply active exceptions only to `seat_overage`, `contractor_overage`, and `sso_gap`.
`reason_codes` is the ordered raw reason-code list after removing exempted controls, or `none`.
`exception_controls` is `none` when empty; otherwise join controls with a comma and no spaces.

Compute `status` with this priority order:

1. `blocked` if `subscription_not_serviceable` remains in `reason_codes`
2. `over_limit` if `seat_overage` or `contractor_overage` remains in `reason_codes`
3. `identity_review` if `sso_gap` remains in `reason_codes`
4. `cleanup` if `expired_invites` remains in `reason_codes`
5. `accepted_exception` if the raw reason-code list was non-empty and all raw overage or SSO
   controls were exempted
6. `renewal_review` if `renewal_days <= 30` and `billable_seats >= 0.9 * seat_limit`
7. `ok` otherwise

Compute `recommended_action` with the same priority:

1. `Restore subscription`
2. `Reduce or approve seat overage`
3. `Reduce or approve contractor access`
4. `Fix SSO enrollment`
5. `Expire stale invitations`
6. `Review accepted exception`
7. `Prepare renewal capacity review`
8. `Monitor`

Compute `seat_delta = billable_seats - seat_limit` and `contractor_delta = contractor_seats -
contractor_limit`.

## `/seat-compliance` HTML Contract

Sort account rows by:

1. status severity: `blocked`, `over_limit`, `identity_review`, `cleanup`, `accepted_exception`,
   `renewal_review`, `ok`
2. `seat_delta` descending
3. account `name` ascending

The rendered page must include:

- `<main data-screen="seat-compliance">`
- an `<h1>` whose text is exactly `Seat Compliance`
- metrics with `data-metric` keys:
  - `accounts`
  - `over-limit`
  - `identity-reviews`
  - `accepted-exceptions`
- a table with `data-table="seat-compliance"`
- one table row per account with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `account`
  - `owner`
  - `plan`
  - `segment`
  - `status`
  - `seat_limit`
  - `billable_seats`
  - `seat_delta`
  - `contractor_limit`
  - `contractor_seats`
  - `contractor_delta`
  - `active_users`
  - `pending_invites`
  - `expired_invites`
  - `sso_gaps`
  - `renewal_days`
  - `open_priority_tickets`
  - `arr`
  - `reason_codes`
  - `exception_controls`
  - `recommended_action`

Metric values should expose a plain numeric value; labeled stat-card markup is acceptable if the
numeric value is the trailing text for the `data-metric` element.

## `/seat-compliance/overages` HTML Contract

Include one row per account where `status != "ok"`. Sort rows by:

1. status severity using the same order as the main screen
2. `seat_delta` descending
3. `contractor_delta` descending
4. account `name` ascending

The rendered page must include:

- `<main data-screen="seat-compliance-overages">`
- an `<h1>` whose text is exactly `Seat Compliance Overages`
- metrics with `data-metric` keys:
  - `review-accounts`
  - `seats-over`
  - `contractors-over`
  - `blocked`
- a table with `data-table="seat-compliance-overages"`
- one table row per included account with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `account`
  - `owner`
  - `status`
  - `seat_delta`
  - `contractor_delta`
  - `sso_gaps`
  - `expired_invites`
  - `open_priority_tickets`
  - `reason_codes`
  - `exception_controls`
  - `recommended_action`

`seats-over` is the sum of positive `seat_delta` values for included rows. `contractors-over` is
the sum of positive `contractor_delta` values for included rows.

## `/seat-compliance/owner-queue` HTML Contract

Aggregate account rows by owner. Sort owner rows by:

1. `escalation_needed == "yes"` before `no`
2. `arr_at_risk` descending
3. owner ascending

The rendered page must include:

- `<main data-screen="seat-compliance-owner-queue">`
- an `<h1>` whose text is exactly `Seat Compliance Owner Queue`
- metrics with `data-metric` keys:
  - `owners`
  - `owners-with-escalations`
  - `seats-over`
  - `arr-at-risk`
- a table with `data-table="seat-compliance-owner-queue"`
- one table row per owner with `data-owner="<owner>"`
- cells in each row with `data-field` keys:
  - `owner`
  - `accounts`
  - `blocked_accounts`
  - `over_limit_accounts`
  - `identity_review_accounts`
  - `accepted_exceptions`
  - `seats_over`
  - `contractors_over`
  - `sso_gaps`
  - `open_priority_tickets`
  - `arr_at_risk`
  - `next_renewal_days`
  - `escalation_needed`

For owner rows:

- `arr_at_risk` is the sum of ARR for owned accounts whose status is not `ok`.
- `next_renewal_days` is the minimum renewal-days value among owned accounts, or blank if none.
- `escalation_needed` is `yes` when the owner has at least one blocked account, at least one
  over-limit account, or at least two identity-review accounts; otherwise it is `no`.

## `/seat-compliance/action-log` HTML Contract

Include one row per account where `status != "ok"`. Sort action rows by:

1. status severity using the same order as the main screen
2. `due_in_days` ascending
3. ARR descending
4. account `name` ascending

For each action row:

- `primary_action` is the same value as the account row's `recommended_action`.
- `due_in_days` is:
  - `0` for `blocked`
  - `3` for `over_limit`
  - `5` for `identity_review`
  - `7` for `cleanup`
  - `10` for `accepted_exception`
  - `14` for `renewal_review`
- `escalation_needed` is `yes` when the account's owner row has `escalation_needed == "yes"`;
  otherwise it is `no`.

The rendered page must include:

- `<main data-screen="seat-compliance-action-log">`
- an `<h1>` whose text is exactly `Seat Compliance Action Log`
- metrics with `data-metric` keys:
  - `action-accounts`
  - `due-now`
  - `owner-escalations`
  - `arr-at-risk`
- a table with `data-table="seat-compliance-action-log"`
- one table row per included account with `data-account-id="<account_id>"`
- cells in each row with `data-field` keys:
  - `account`
  - `owner`
  - `status`
  - `reason_codes`
  - `exception_controls`
  - `primary_action`
  - `due_in_days`
  - `escalation_needed`
  - `arr`

For the action-log metrics:

- `action-accounts` is the number of action-log rows.
- `due-now` is the number of action-log rows with `due_in_days == 0`.
- `owner-escalations` is the number of action-log rows whose `escalation_needed` value is `yes`.
  It is not the count of distinct owners.
- `arr-at-risk` is the sum of ARR for all action-log rows.

## Seat Compliance Export Contract

The `--export-seat-compliance` command writes a JSON object with exactly these top-level keys:

- `schema_version`: exactly `seat_compliance_export.v1`
- `summary`: the same four metric keys and values as `/seat-compliance/action-log`
- `actions`: the exact action rows from `/seat-compliance/action-log`, in the same order and with
  the same fields
- `owner_queue`: the exact owner rows from `/seat-compliance/owner-queue`, in the same order and
  with the same fields

Write JSON with two-space indentation, sorted object keys, and a trailing newline.

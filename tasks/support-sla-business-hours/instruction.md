The support SLA report has grown into an account-level SLA operations package. It must compute
ticket SLA clocks under business hours, apply customer-wait pauses, subtract account outage
exemptions, apply segment entitlement multipliers, account for escalation handling, and emit both
ticket-level and account-level artifacts.

Run shape:

```sh
python -m sla_report.cli --input-dir <input> --output-dir <output>
```

Inputs:

- `tickets.csv` with columns exactly
  `ticket_id,account_id,priority,channel,opened_at,first_response_at,resolved_at,owner_team`.
- `events.csv` with columns exactly `ticket_id,event_type,at`.
- `calendar.json` with `timezone`, `business_start`, `business_end`, `holidays`, and
  `thresholds_by_priority`.
- `accounts.csv` with columns exactly
  `account_id,segment,region,success_manager`.
- `entitlements.csv` with columns exactly
  `segment,response_multiplier,resolution_multiplier,response_credit_cents,resolution_credit_cents,executive_review`.
- `outage_windows.csv` with columns exactly
  `outage_id,account_id,start_at,end_at,exempt_response,exempt_resolution`.
- `escalations.csv` with columns exactly
  `ticket_id,escalation_level,opened_at,closed_at,owner`.

Rules:

- Interpret all timestamps in `calendar.json`'s timezone.
- Business hours are Monday through Friday, from `business_start` inclusive to `business_end`
  exclusive.
- Dates listed in `holidays` are not business days.
- Count business minutes by overlap with business windows. Do not count weekends, holidays, or time
  outside the business window.
- `business_minutes_to_first_response` is business minutes from `opened_at` to
  `first_response_at`.
- `business_minutes_to_resolution` is business minutes from `opened_at` to `resolved_at`, minus
  paused business minutes.
- Pause intervals come from matching `waiting_on_customer_start` and `waiting_on_customer_end`
  events in timestamp order for the same ticket.
- If a `waiting_on_customer_start` event appears while the ticket is already waiting on the
  customer, treat the additional start as a duplicate signal. It does not open a nested or second
  pause interval; the next `waiting_on_customer_end` closes the current pause.
- If a wait has no matching end, it runs until `resolved_at`.
- Pause time only subtracts from the resolution clock. It does not subtract from first response.
- Outage windows apply only to tickets for the same `account_id`.
- If `exempt_response` is `true`, subtract the business-minute overlap between that outage and the
  ticket's opened-to-first-response interval from the response clock.
- If `exempt_resolution` is `true`, subtract the business-minute overlap between that outage and
  the ticket's opened-to-resolved interval from the resolution clock.
- Outage exemption minutes do not change `paused_business_minutes`; they are tracked separately.
- The `business_minutes_to_first_response` output column is the net response clock after subtracting
  response outage exemptions.
- The `business_minutes_to_resolution` output column is the net resolution clock after subtracting
  paused business minutes and resolution outage exemptions.
- Do not emit separate gross clock columns.
- Effective thresholds are:
  - priority threshold from `calendar.json`
  - multiplied by the account segment's `response_multiplier` or `resolution_multiplier`
  - rounded down to an integer number of minutes.
- `response_breached` is `true` when net response minutes are greater than the effective response
  threshold.
- `resolution_breached` is `true` when net resolution minutes are greater than the effective
  resolution threshold.
- Ticket `credit_cents` is the segment `response_credit_cents` when `response_breached` is true,
  plus `resolution_credit_cents` when `resolution_breached` is true.
- Escalation rows are matched by `ticket_id`. Blank `closed_at` means the escalation remains open
  until the ticket's `resolved_at` for business-minute calculation and has `open_escalation=true`.
- Escalation business minutes are business minutes across each escalation interval, clipped to the
  ticket's opened/resolved interval, then summed.
- `review_required` is `true` for a ticket when any of these is true:
  - the ticket has any breach and the segment entitlement has `executive_review=true`
  - the ticket is `p1` and has a resolution breach
  - the ticket has an open escalation
- `breach_reasons` is a pipe-separated list in this exact order, omitting absent reasons:
  `response`, `resolution`, `open_escalation`.
- Re-running into an existing output directory must overwrite deterministic files rather than
  appending duplicate rows.

Outputs:

- `ticket_sla.csv`
- `account_sla_summary.csv`
- `escalation_audit.csv`
- `breach_summary.json`

`ticket_sla.csv` columns are exactly:

`ticket_id,account_id,priority,segment,owner_team,business_minutes_to_first_response,business_minutes_to_resolution,paused_business_minutes,outage_exempt_response_minutes,outage_exempt_resolution_minutes,effective_response_threshold,effective_resolution_threshold,response_breached,resolution_breached,credit_cents,review_required,breach_reasons`

Rows are sorted by `ticket_id`. Boolean values are lowercase `true` or `false`.

`account_sla_summary.csv` columns are exactly:

`account_id,segment,tickets,response_breaches,resolution_breaches,credits_cents,review_required,worst_priority,total_paused_business_minutes,total_outage_exempt_minutes`

Rows are sorted by `account_id`.

- `review_required` is `true` if any ticket for the account has `review_required=true`.
- `worst_priority` is the highest-severity priority present for the account, using `p1`, then `p2`,
  then `p3`, then lexical order for unknown priorities.
- `total_outage_exempt_minutes` is response outage exemptions plus resolution outage exemptions for
  the account.

`escalation_audit.csv` columns are exactly:

`ticket_id,escalation_count,escalation_business_minutes,open_escalation,owners,review_required,breach_reasons`

Rows are sorted by `ticket_id` and include every ticket that has at least one escalation row or at
least one breach. `owners` is the sorted unique escalation owners joined with `|`; it is blank when
there are no escalation owners.

`breach_summary.json` has exactly these keys:

- `tickets`
- `accounts`
- `response_breaches`
- `resolution_breaches`
- `any_breaches`
- `credits_cents`
- `review_required_accounts`
- `total_paused_business_minutes`
- `total_outage_exempt_minutes`
- `breached_ticket_ids`
- `generated_for_timezone`

`response_breaches` and `resolution_breaches` count only their matching boolean columns.
`any_breaches` counts tickets whose `breach_reasons` field is nonempty, including tickets whose
only reason is `open_escalation`. `breached_ticket_ids` is the sorted list of those same ticket IDs.

Keep the existing CLI module and package name.

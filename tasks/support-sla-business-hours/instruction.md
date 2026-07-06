The support SLA report needs to use a business-hours calendar instead of elapsed wall-clock time.

Run shape:

```sh
python -m sla_report.cli --input-dir <input> --output-dir <output>
```

Inputs:

- `tickets.csv` with columns exactly
  `ticket_id,priority,opened_at,first_response_at,resolved_at`.
- `events.csv` with columns exactly `ticket_id,event_type,at`.
- `calendar.json` with `timezone`, `business_start`, `business_end`, `holidays`, and
  `thresholds_by_priority`.

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
- `response_breached` is `true` when response minutes are greater than the priority's
  `response_minutes` threshold.
- `resolution_breached` is `true` when resolution minutes are greater than the priority's
  `resolution_minutes` threshold.
- Re-running into an existing output directory must overwrite deterministic files rather than
  appending duplicate rows.

Outputs:

- `ticket_sla.csv`
- `breach_summary.json`

`ticket_sla.csv` columns are exactly:

`ticket_id,priority,business_minutes_to_first_response,business_minutes_to_resolution,paused_business_minutes,response_breached,resolution_breached`

Rows are sorted by `ticket_id`. Boolean values are lowercase `true` or `false`.

`breach_summary.json` has exactly these keys:

- `tickets`
- `response_breaches`
- `resolution_breaches`
- `any_breaches`
- `total_paused_business_minutes`

Keep the existing CLI module and package name.

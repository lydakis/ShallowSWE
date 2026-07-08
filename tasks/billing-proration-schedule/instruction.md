# Build Billing Proration Schedule

Read `input/subscription_events.csv` and write a proration schedule under `output/`.

Implement the operation in `scripts/build_schedule.py`; the verifier reruns that script on fresh
local inputs.

Input columns:

- `account_id`
- `event_id`
- `event_date`
- `period_start`
- `period_end`
- `old_plan`
- `new_plan`
- `old_monthly_cents`
- `new_monthly_cents`

Rules:

- Dates are ISO dates.
- `period_end` is exclusive.
- `period_days = period_end - period_start`.
- `remaining_days = period_end - event_date`.
- Use actual calendar days, not a fixed 30-day month.
- `action` is `upgrade` when the new monthly price is higher, `downgrade` when lower, `cancel` when the new plan is `cancelled`, otherwise `noop`.
- Skip `noop` rows from `schedule.csv`, but count them in `summary.json` as events.
- For `cancel`, treat the new monthly price as `0` even if the CSV has a value.
- `amount_usd_cents = round_half_up((new_monthly_cents - old_monthly_cents) * remaining_days / period_days)`.
- Negative amounts are credits. Positive amounts are charges.
- Sort schedule rows by `account_id`, then `event_id`.
- Write `output/schedule.csv` with columns:
  `account_id,event_id,action,effective_start,effective_end,period_days,remaining_days,amount_usd_cents`.
- Write `output/summary.json` with keys `event_count`, `line_item_count`, `total_charge_cents`, `total_credit_cents`, and `net_total_cents`.
- `total_credit_cents` is a positive number containing the absolute value of negative schedule rows.

Keep the work local to this repository. Do not use network access.

The billing migration command needs to emit the v4 ledger evidence package for mixed v1/v2/v3
inputs while keeping the existing v1-only and v2-only migrations working.

Run shape:

```sh
python -m ledger_migrator.cli --input-dir <input> --output-dir <output>
```

Required input files:

- `accounts.csv`: `account_id,status,plan_id,region,segment`
- `plans.json`: array of `{ "plan_id", "currency", "unit_price_cents", "tax_rate_basis_points", "recognition_rule" }`
- `usage.jsonl`: one JSON object per usage event
- `exchange_rates.csv`: `currency,to_usd_rate_micros`

Optional input files should be treated as empty when absent:

- `discounts.csv`: `discount_code,percent_bps,applies_to_plan`
- `credits.csv`: `credit_id,account_id,currency,amount_cents,issued_at,reason`
- `legacy_adjustments.csv`: `adjustment_id,account_id,currency,amount_cents,reason,effective_at`
- `account_overrides.csv`: `account_id,status_override,plan_override_id,effective_at`

Usage event formats:

- v1: `version=1`, `usage_id`, `account_id`, `units`, `occurred_at`; use the account's effective plan and source `legacy`.
- v2: `version=2`, `usage_id`, `account_id`, `plan_id`, `units`, `occurred_at`, `source`, optional `discount_code`.
- v3: `version=3`, `usage_id`, `account_id`, optional `plan_id`, `quantity`, optional `unit_price_cents`, `occurred_at`, `source`, optional `discount_code`, optional `idempotency_key`.

Outputs:

- `normalized_events.jsonl`
- `ledger.csv`
- `account_balances.csv`
- `plan_revenue.csv`
- `rejects.csv`
- `migration_audit.json`

Output schemas:

- `normalized_events.jsonl` rows have exactly these keys: `event_id`, `account_id`, `plan_id`, `units`, `currency`, `gross_cents`, `discount_cents`, `tax_cents`, `net_cents`, `usd_net_micros`, `source`, `occurred_at`, `recognition_month`.
- `ledger.csv` columns are exactly `account_id,currency,event_id,event_type,amount_cents,amount_usd_micros,running_balance_cents,running_balance_usd_micros,recognition_month`.
- `account_balances.csv` columns are exactly `account_id,region,segment,currency,ending_balance_cents,ending_balance_usd_micros,status`.
- `plan_revenue.csv` columns are exactly `recognition_month,plan_id,currency,gross_cents,discount_cents,tax_cents,net_cents,net_usd_micros`.
- `rejects.csv` columns are exactly `input,event_id,reason`.
- `migration_audit.json` has exactly these keys: `schema_version`, `source_files`, `normalized_events`, `ledger_rows`, `account_balance_rows`, `plan_revenue_rows`, `reject_count`, `currencies`, `net_usd_micros`, `generated_at`.

Rules:

- `schema_version` is `v4` and `generated_at` is the literal string `deterministic`.
- Apply account overrides whose `effective_at` is less than or equal to the event timestamp.
  `status_override` changes effective status when non-empty; `plan_override_id` changes effective
  plan when non-empty.
- Only effectively active accounts can produce usage, adjustment, or credit ledger rows.
- Usage units must be a positive integer. v3 uses `quantity` as units.
- Unknown account rejects use reason `UNKNOWN_ACCOUNT`.
- Suspended account rejects use reason `SUSPENDED_ACCOUNT`.
- Unknown plan rejects use reason `UNKNOWN_PLAN`.
- Non-positive or non-integer usage rejects use reason `INVALID_UNITS`.
- Duplicate `usage_id` rejects use reason `DUPLICATE_USAGE_ID`; keep the first valid event and
  reject later duplicates.
- Duplicate non-empty v3 `idempotency_key` rejects use reason `DUPLICATE_IDEMPOTENCY_KEY`; keep the
  first valid event with that key.
- Unknown discount codes reject usage with reason `UNKNOWN_DISCOUNT`.
- Discounts whose `applies_to_plan` is non-empty and does not match the effective plan reject usage
  with reason `DISCOUNT_PLAN_MISMATCH`.
- Unknown currencies reject rows with reason `UNKNOWN_CURRENCY`.
- Zero or non-integer credit and adjustment amounts reject with reason `INVALID_AMOUNT`.
- v3 `unit_price_cents` overrides the plan unit price for that event only.
- `discount_cents` is `floor(gross_cents * percent_bps / 10000)`.
- `tax_cents` is `floor((gross_cents - discount_cents) * tax_rate_basis_points / 10000)`.
- `net_cents` is `gross_cents - discount_cents + tax_cents`.
- `amount_usd_micros` and `usd_net_micros` are `round_half_up(amount_cents * to_usd_rate_micros / 100)`.
- `recognition_month` is the first seven characters of the event timestamp, such as `2026-01`.
- `normalized_events.jsonl` contains accepted usage events only, sorted by `occurred_at`, then `event_id`.
- `ledger.csv` is grouped by `account_id`, then `currency`. Within each group, accepted usage rows
  are ordered by `occurred_at` then `event_id`, then adjustments by `effective_at` then
  `adjustment_id`, then credits by `issued_at` then `credit_id`.
- Adjustment rows use event type `adjustment` and their signed amount.
- Credits use event type `credit`; the output amount is negative and capped so the running balance
  for that account and currency never goes below zero.
- `account_balances.csv` has one row per account/currency group with accepted ledger rows, sorted by
  `account_id`, then `currency`. Its `status` is the account status after applying the latest
  override for that account, or the base status if no override exists.
- `plan_revenue.csv` includes accepted usage rows only, grouped by `recognition_month`, `plan_id`,
  and `currency`, sorted by those columns.
- `rejects.csv` input values are exactly `usage`, `adjustment`, or `credit`, sorted by `input`, then
  `event_id`.
- `source_files` is the sorted list of input file names that exist in the input directory.
- `currencies` is the sorted list of currencies appearing in accepted ledger rows.
- `migration_audit.json` `net_usd_micros` is the sum of `amount_usd_micros` across all accepted
  `ledger.csv` rows, including usage, adjustment, and capped credit rows.

Keep the existing v1-only and v2-only migrations working. Missing optional files should be treated
as empty inputs.

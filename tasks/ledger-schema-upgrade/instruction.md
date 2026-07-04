The billing migration command needs to emit the v3 ledger package for mixed v1/v2 inputs.

Run shape:

```sh
python -m ledger_migrator.cli --input-dir <input> --output-dir <output>
```

Input files:

- `accounts.csv`: `account_id,status,plan_id`
- `plans.json`: array of `{ "plan_id", "currency", "unit_price_cents" }`
- `usage.jsonl`: one JSON object per usage event
- `credits.csv`: optional, `credit_id,account_id,amount_cents`
- `legacy_adjustments.csv`: optional, `adjustment_id,account_id,amount_cents,reason`

Usage event formats:

- v1: `version=1`, `usage_id`, `account_id`, `units`, `occurred_at`; use the account's `plan_id` and source `legacy`.
- v2: `version=2`, `usage_id`, `account_id`, `plan_id`, `units`, `occurred_at`, `source`.

Output files:

- `normalized_events.jsonl`
- `ledger.csv`
- `rejects.csv`
- `summary.json`

Rules:

- Only active accounts can produce ledger rows.
- Usage `units` must be a positive integer.
- Unknown account rejects use reason `UNKNOWN_ACCOUNT`.
- Suspended account rejects use reason `SUSPENDED_ACCOUNT`.
- Unknown plan rejects use reason `UNKNOWN_PLAN`.
- Non-positive or non-integer usage rejects use reason `INVALID_UNITS`.
- Duplicate `usage_id` rejects use reason `DUPLICATE_USAGE_ID`; keep the first valid event and reject later duplicates.
- Usage gross cents is `units * unit_price_cents`.
- `normalized_events.jsonl` contains valid usage events only, sorted by `occurred_at`, then `event_id`.
- Each normalized event has exactly these keys: `event_id`, `account_id`, `plan_id`, `units`, `currency`, `gross_cents`, `source`, `occurred_at`.
- `ledger.csv` columns are exactly `account_id,event_id,event_type,amount_cents,running_balance_cents`.
- Ledger rows are grouped by ascending `account_id`.
- For each account, ledger rows are ordered as valid usage events by `occurred_at` then `event_id`, then adjustments by `adjustment_id`, then credits by `credit_id`.
- Adjustment rows use event type `adjustment` and their signed `amount_cents`.
- Credits apply last and use event type `credit`. A credit row amount is negative and capped so an account balance never goes below zero.
- Credits and adjustments for unknown or non-active accounts go to `rejects.csv`.
- `rejects.csv` columns are exactly `input,event_id,reason`, sorted by `input`, then `event_id`.
- `rejects.csv` input values are exactly `usage`, `adjustment`, or `credit`.
- `summary.json` reports `usage_events`, `adjustment_events`, `credit_events`, `reject_count`, `gross_cents`, `adjustment_cents`, `credit_cents`, and `net_cents`.
- Summary event counts and totals include accepted ledger rows only; rejected input rows count only toward `reject_count`.

Keep the existing v1-only and v2-only migrations working. Missing optional credit or adjustment
files should be treated as empty inputs.

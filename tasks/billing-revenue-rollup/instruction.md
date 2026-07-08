# Build Billing Revenue Close Package

Create deterministic revenue close artifacts under `output/` from the billing files in `input/`.

Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh visible
and hidden inputs. Keep the work local to this repository. Do not use network access.

## Inputs

The script must read:

- `input/accounts.csv`: `account_id,segment,region,manager`
- `input/fx_rates.csv`: `currency,rate_to_usd`
- `input/contracts.csv`:
  `contract_id,account_id,currency,committed_amount,contract_start,contract_end`
- `input/invoices.csv`:
  `invoice_id,account_id,plan,currency,amount,status,invoice_date,service_start,service_end`
- `input/credits.csv`: `credit_id,invoice_id,currency,amount,issued_at,reason`
- `input/disputes.csv`: `dispute_id,invoice_id,currency,amount,status,opened_at`
- `input/payments.csv`: `payment_id,invoice_id,currency,amount,status,received_at`

## Money And Date Rules

- Convert every money amount to USD cents using `amount * rate_to_usd`, rounded half-up to cents.
- Format CSV money fields as strings with exactly two decimal places.
- Format JSON money fields as strings with exactly two decimal places.
- `period` is `YYYY-MM`.
- Service date ranges are inclusive.
- Only invoices whose `status` is `paid` produce recognized revenue.
- Allocate each paid invoice's gross USD cents across service months by inclusive service-day
  overlap. For each period except the last period touched by the service range, allocate
  `gross_cents * overlap_days // total_service_days`. Allocate any remaining cents to the last
  period, so period cents sum exactly to the invoice gross cents.
- Credits reduce recognized revenue in the period of `issued_at` and inherit the invoice plan and
  account. Credits for unknown or non-paid invoices are rejected.
- Only disputes whose `status` is `open` are listed as open disputes. Open disputes inherit the
  invoice plan and account and use the period of `opened_at`. Open disputes do not reduce net
  recognized revenue. Disputes for unknown or non-paid invoices are rejected.
- Only payments whose `status` is `settled` are applied. Settled payments for unknown or non-paid
  invoices are rejected. Payments whose status is not `settled` are ignored and are not rejected.
- Contract commitments are converted to USD cents from `committed_amount` and `currency`.
- Each account has at most one row in `contracts.csv`.
- Negative money values are formatted with a leading `-`, for example `-12.34`.

## Outputs

Write exactly these files under `output/`:

- `summary.json`
- `revenue_rollup.csv`
- `account_exposure.csv`
- `adjustments.csv`
- `cash_application.csv`
- `contract_variance.csv`
- `rejects.csv`
- `close_audit.json`

### `revenue_rollup.csv`

Columns are exactly:

`period,plan,gross_usd,credits_usd,open_disputes_usd,net_usd`

Rows are grouped by `period` and `plan` for every period/plan pair that has gross revenue, credits,
or open disputes. Sort rows by `period`, then `plan`. `net_usd` is `gross_usd - credits_usd`.

### `account_exposure.csv`

Columns are exactly:

`account_id,segment,region,manager,recognized_usd,open_disputes_usd,net_at_risk_usd,status`

Include every account that has a paid invoice, valid credit, or valid open dispute. Sort by
`account_id`. `recognized_usd` is account gross revenue minus valid credits. `open_disputes_usd`
is valid open dispute amount. `net_at_risk_usd` equals `recognized_usd` when
`open_disputes_usd > 0`, otherwise `0.00`. `status` is `disputed` when `open_disputes_usd > 0`,
otherwise `clear`.

### `adjustments.csv`

Columns are exactly:

`adjustment_id,invoice_id,account_id,type,amount_usd,status,period`

Include valid credits and valid open disputes only. Credit rows use `type=credit` and
`status=applied`. Open dispute rows use `type=dispute` and `status=open`. Sort by `period`, then
`type`, then `adjustment_id`.

### `cash_application.csv`

Columns are exactly:

`account_id,invoice_id,period,invoice_net_usd,settled_payments_usd,open_ar_usd,status`

Include every paid invoice. `invoice_net_usd` is invoice gross USD minus valid credits attached to
that invoice. `settled_payments_usd` is the sum of valid settled payments attached to that invoice.
`open_ar_usd` is `max(invoice_net_usd - settled_payments_usd, 0)`. `period` is the period of
`invoice_date`. `status` is `paid_in_full` when `open_ar_usd == 0`, otherwise `open`. Sort by
`account_id`, then `invoice_id`.

### `contract_variance.csv`

Columns are exactly:

`account_id,contract_id,manager,contracted_usd,net_recognized_usd,settled_payments_usd,open_ar_usd,variance_usd,status`

Include every account that appears in `contracts.csv`, plus any account that has paid invoice
activity. If an account has no contract, use an empty string for `contract_id` and `0.00` for
`contracted_usd`. `net_recognized_usd` is account gross revenue minus valid credits.
`settled_payments_usd` is valid settled payments for the account. `open_ar_usd` is the sum of the
invoice-level open AR from `cash_application.csv`. `variance_usd` is
`net_recognized_usd - contracted_usd`. `status` is:

- `under_committed` when variance is less than zero.
- `over_committed` when variance is greater than zero.
- `on_target` when variance is exactly zero.

Sort by `account_id`, then `contract_id`.

### `rejects.csv`

Columns are exactly:

`input,event_id,reason`

Reject reasons are:

- `unknown_invoice`: a credit, dispute, or settled payment references an invoice id not present in
  `invoices.csv`.
- `invoice_not_paid`: a credit, open dispute, or settled payment references an invoice whose status
  is not `paid`.

Sort rejects by `input`, then `event_id`. `input` is `credit`, `dispute`, or `payment`.

### `summary.json`

Top-level keys are exactly:

- `accounts_at_risk`: count of account exposure rows whose `status` is `disputed`.
- `credits_usd`: total valid credits.
- `gross_revenue_usd`: total recognized gross revenue before credits.
- `net_revenue_usd`: total net recognized revenue after credits.
- `open_disputes`: count of valid open disputes.
- `open_disputes_usd`: total valid open disputes.
- `open_ar_usd`: total open accounts receivable from `cash_application.csv`.
- `settled_payments_usd`: total valid settled payments.
- `contracted_usd`: total contract commitment USD.
- `contract_variance_usd`: total `net_recognized_usd - contracted_usd` across
  `contract_variance.csv`.
- `periods`: sorted list of periods present in `revenue_rollup.csv`.
- `plans`: sorted list of plans present in `revenue_rollup.csv`.
- `rejected_adjustments`: reject row count.

All objects and arrays in `summary.json` must be written deterministically.

### `close_audit.json`

Top-level keys are exactly:

- `generated_at`: the literal string `deterministic`.
- `input_rows`: object with counts for `accounts`, `contracts`, `invoices`, `credits`, `disputes`,
  and `payments`.
- `output_rows`: object with counts for `revenue_rollup`, `account_exposure`, `adjustments`,
  `cash_application`, `contract_variance`, and `rejects`.
- `control_totals`: object with `gross_revenue_usd`, `credits_usd`, `net_revenue_usd`,
  `settled_payments_usd`, `open_ar_usd`, `contracted_usd`, and `contract_variance_usd`.
- `periods`: sorted list of periods present in `revenue_rollup.csv`.
- `plans`: sorted list of plans present in `revenue_rollup.csv`.

The money totals in `close_audit.json` must match the corresponding totals in `summary.json` and
the output CSV files.

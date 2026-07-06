The invoice import package now receives invoices from three local sources. Extend the existing
public API and CLI so they merge all sources deterministically instead of only reading CSV.

Run shape:

```sh
python -m invoice_merge.cli --input-dir <input> --output-dir <output>
```

Inputs:

- `csv_invoices.csv`
- `api_invoices.json`
- `legacy_invoices.txt`
- `currency_rates.json`

CSV columns:

`invoice_id,customer,amount,currency,status,issued_at,updated_at`

API JSON is an array of objects with:

- `id`
- `account.name`
- `money.value`
- `money.currency`
- `state`
- `issued`
- `updated`

Legacy lines are pipe-delimited:

`invoice_id|customer|amount_cents|currency|status|issued_yyyymmdd|updated_yyyymmdd`

Rules:

- Keep the public `invoice_merge.importer.import_invoices(input_dir)` function name.
- `invoice_id` is normalized by stripping whitespace and uppercasing.
- Merge duplicate invoice IDs by source precedence: API beats CSV, CSV beats legacy.
- If duplicate records have the same source precedence, keep the record with the latest
  `updated_at`; if still tied, keep the later record in that source file.
- Normalize status values:
  - `paid` and `settled` become `paid`
  - `open`, `pending`, and `draft` become `open`
  - `void`, `canceled`, and `cancelled` become `void`
- Reject rows with a missing invoice ID, unknown status, unknown currency, malformed dates, or
  non-positive amount.
- Amounts from CSV and API are decimal major units. Legacy amounts are integer cents.
- Normalize every kept invoice amount to USD cents using `currency_rates.json`. The rates map
  currency code to USD conversion rate. Round half up to the nearest cent.
- Output `merged_invoices.csv`, `rejected_invoices.csv`, and `summary.json`.
- Re-running into an existing output directory must overwrite deterministic files.
- Add a focused regression test under `tests/` that is discovered by
  `python -m unittest discover -s tests` and fails if the importer ignores API/legacy precedence
  and only reads the CSV source.

`merged_invoices.csv` columns are exactly:

`invoice_id,customer,amount_usd_cents,status,issued_at,updated_at,source`

Rows are sorted by `invoice_id`.

`rejected_invoices.csv` columns are exactly:

`source,row_ref,invoice_id,reason`

Allowed `reason` values are exactly:

- `missing_invoice_id`
- `unknown_status`
- `unknown_currency`
- `malformed_date`
- `non_positive_amount`

Rejected rows are sorted by source order (`api`, `csv`, `legacy`) and then by row number within the
source. `row_ref` is the 1-based row number within that source payload. For API, use the array
position starting at 1. For CSV, count data rows starting at 1, not the header. For legacy, count
non-empty lines starting at 1.

`summary.json` has exactly these keys:

- `invoice_count`
- `paid_total_usd_cents`
- `open_total_usd_cents`
- `void_total_usd_cents`
- `rejected_count`

Keep the existing CLI module and package name. Do not use network access.

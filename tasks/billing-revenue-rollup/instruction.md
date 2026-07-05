# Build Billing Revenue Rollup

Create revenue rollup artifacts under `output/` from the billing files in `input/`. Credits reduce recognized revenue; open disputes are listed separately.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Revenue is grouped by plan and net of credits.
- Open disputes are listed in adjustments.
- Summary total recognized revenue matches the rollup.
- Write exactly these files under `output/`:
  - `summary.json` with keys `open_disputes` and `recognized_revenue`.
  - `revenue_rollup.csv` with columns `plan,gross,credits,net`.
  - `adjustments.csv` with columns `dispute_id,invoice_id,amount,status`.
- Include only paid invoices in recognized revenue.
- Format CSV money fields with two decimal places.
- Sort the revenue rollup rows by `plan`.

Keep the work local to this repository. Do not use network access.

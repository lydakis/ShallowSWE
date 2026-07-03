The payout reconciliation job is producing the wrong report for operations.

Fix the pipeline so `python -m payout_reconcile.cli --input-dir /app/data --output-dir /app/output` writes:

- `payouts.csv` with columns `customer_id,customer_name,invoice_id,paid_amount,refund_amount,net_amount`
- `rejects.csv` with columns `source,record_id,reason`

Rules:

- Include only paid invoices whose customer exists.
- Join refunds by `invoice_id`; missing refunds count as `0.00`.
- `net_amount` is paid amount minus refund amount.
- Reject payments for unknown invoices with reason `unknown_invoice`.
- Reject paid invoices whose customer is missing with reason `unknown_customer`.
- Sort `payouts.csv` by `customer_id`, then `invoice_id`. Sort `rejects.csv` by `source`, then `record_id`.

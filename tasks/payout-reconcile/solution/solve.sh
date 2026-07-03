#!/usr/bin/env bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path

path = Path("payout_reconcile/reconcile.py")
text = path.read_text()
old = '''    payments = read_json(input_path / "payments.json")

    payout_rows: list[dict[str, str]] = []
    reject_rows: list[dict[str, str]] = []

    for payment in payments:
        invoice_id = str(payment["invoice_id"])
        invoice = invoices.get(invoice_id)
        if invoice is None:
            reject_rows.append(
                {
                    "source": "payment",
                    "record_id": str(payment["payment_id"]),
                    "reason": "unknown_invoice",
                }
            )
            continue

        customer_id = invoice["customer_id"]
        payout_rows.append(
            {
                "customer_id": customer_id,
                "customer_name": customers.get(customer_id, ""),
                "invoice_id": invoice_id,
                "paid_amount": f"{float(payment['amount']):.2f}",
                "refund_amount": "0.00",
                "net_amount": f"{float(payment['amount']):.2f}",
            }
        )

    write_csv(output_path / "payouts.csv", PAYOUT_FIELDS, payout_rows)
    write_csv(output_path / "rejects.csv", REJECT_FIELDS, reject_rows)
'''
new = '''    payments = read_json(input_path / "payments.json")
    refunds_by_invoice: dict[str, float] = {}
    for refund in read_csv(input_path / "refunds.csv"):
        refunds_by_invoice[refund["invoice_id"]] = (
            refunds_by_invoice.get(refund["invoice_id"], 0.0) + float(refund["amount"])
        )

    payout_rows: list[dict[str, str]] = []
    reject_rows: list[dict[str, str]] = []

    payments_by_invoice = {str(payment["invoice_id"]): payment for payment in payments}

    for invoice_id, invoice in invoices.items():
        customer_id = invoice["customer_id"]
        if customer_id not in customers:
            reject_rows.append(
                {
                    "source": "invoice",
                    "record_id": invoice_id,
                    "reason": "unknown_customer",
                }
            )
            continue
        payment = payments_by_invoice.get(invoice_id)
        if payment is None:
            continue
        paid_amount = float(payment["amount"])
        refund_amount = refunds_by_invoice.get(invoice_id, 0.0)
        payout_rows.append(
            {
                "customer_id": customer_id,
                "customer_name": customers[customer_id],
                "invoice_id": invoice_id,
                "paid_amount": f"{paid_amount:.2f}",
                "refund_amount": f"{refund_amount:.2f}",
                "net_amount": f"{paid_amount - refund_amount:.2f}",
            }
        )

    for payment in payments:
        invoice_id = str(payment["invoice_id"])
        if invoice_id not in invoices:
            reject_rows.append(
                {
                    "source": "payment",
                    "record_id": str(payment["payment_id"]),
                    "reason": "unknown_invoice",
                }
            )

    payout_rows.sort(key=lambda row: (row["customer_id"], row["invoice_id"]))
    reject_rows.sort(key=lambda row: (row["source"], row["record_id"]))

    write_csv(output_path / "payouts.csv", PAYOUT_FIELDS, payout_rows)
    write_csv(output_path / "rejects.csv", REJECT_FIELDS, reject_rows)
'''
path.write_text(text.replace(old, new))
PY

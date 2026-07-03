from __future__ import annotations

from pathlib import Path

from .io import read_csv, read_json, write_csv


PAYOUT_FIELDS = [
    "customer_id",
    "customer_name",
    "invoice_id",
    "paid_amount",
    "refund_amount",
    "net_amount",
]
REJECT_FIELDS = ["source", "record_id", "reason"]


def reconcile(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    customers = {
        row["customer_id"]: row["customer_name"]
        for row in read_csv(input_path / "customers.csv")
    }
    invoices = {
        row["invoice_id"]: row
        for row in read_csv(input_path / "invoices.csv")
        if row["status"] == "paid"
    }
    payments = read_json(input_path / "payments.json")

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

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/payout_reconcile/reconcile.py" <<'PY'
from __future__ import annotations

from collections import defaultdict
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

    customers = {row["customer_id"]: row["customer_name"] for row in read_csv(input_path / "customers.csv")}
    paid_invoices = {
        row["invoice_id"]: row
        for row in read_csv(input_path / "invoices.csv")
        if row["status"] == "paid"
    }
    refunds = _refund_totals(input_path / "refunds.csv")
    payments = read_json(input_path / "payments.json")
    payments_by_invoice = {str(row["invoice_id"]): row for row in payments}

    payouts: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []

    for invoice_id, invoice in paid_invoices.items():
        customer_id = invoice["customer_id"]
        if customer_id not in customers:
            rejects.append({"source": "invoice", "record_id": invoice_id, "reason": "unknown_customer"})
            continue

        payment = payments_by_invoice.get(invoice_id)
        if payment is None:
            continue

        paid_amount = float(payment["amount"])
        refund_amount = refunds[invoice_id]
        payouts.append(
            {
                "customer_id": customer_id,
                "customer_name": customers[customer_id],
                "invoice_id": invoice_id,
                "paid_amount": _fmt(paid_amount),
                "refund_amount": _fmt(refund_amount),
                "net_amount": _fmt(paid_amount - refund_amount),
            }
        )

    for payment in payments:
        invoice_id = str(payment["invoice_id"])
        if invoice_id not in paid_invoices:
            rejects.append(
                {
                    "source": "payment",
                    "record_id": str(payment["payment_id"]),
                    "reason": "unknown_invoice",
                }
            )

    payouts.sort(key=lambda row: (row["customer_id"], row["invoice_id"]))
    rejects.sort(key=lambda row: (row["source"], row["record_id"]))
    write_csv(output_path / "payouts.csv", PAYOUT_FIELDS, payouts)
    write_csv(output_path / "rejects.csv", REJECT_FIELDS, rejects)


def _refund_totals(path: Path) -> defaultdict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    for row in read_csv(path):
        totals[row["invoice_id"]] += float(row["amount"])
    return totals


def _fmt(value: float) -> str:
    return f"{value:.2f}"
PY

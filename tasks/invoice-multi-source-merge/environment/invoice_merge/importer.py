from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    customer: str
    amount_usd_cents: int
    status: str
    issued_at: str
    updated_at: str
    source: str


def import_invoices(input_dir: str | Path) -> tuple[list[Invoice], list[dict[str, str]]]:
    """Seed implementation: CSV-only and intentionally incomplete."""
    root = Path(input_dir)
    invoices: list[Invoice] = []
    rejects: list[dict[str, str]] = []
    rates = json.loads((root / "currency_rates.json").read_text())
    with (root / "csv_invoices.csv").open(newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=1):
            try:
                amount = float(row["amount"]) * float(rates[row["currency"].strip().upper()])
                invoices.append(
                    Invoice(
                        invoice_id=row["invoice_id"].strip().upper(),
                        customer=row["customer"].strip(),
                        amount_usd_cents=round(amount * 100),
                        status=row["status"].strip().lower(),
                        issued_at=row["issued_at"].strip(),
                        updated_at=row["updated_at"].strip(),
                        source="csv",
                    )
                )
            except Exception:
                rejects.append(
                    {
                        "source": "csv",
                        "row_ref": str(index),
                        "invoice_id": row.get("invoice_id", "").strip().upper(),
                        "reason": "invalid_row",
                    }
                )
    return invoices, rejects

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    customer: str
    amount: float
    status: str


def import_invoices(path: str | Path) -> list[Invoice]:
    invoices: list[Invoice] = []
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            invoices.append(
                Invoice(
                    invoice_id=row["invoice_id"].strip(),
                    customer=row["customer"].strip(),
                    amount=float(row["amount"]),
                    status=row["status"].strip().lower(),
                )
            )
    return invoices

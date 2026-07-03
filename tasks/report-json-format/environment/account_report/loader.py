from __future__ import annotations

import csv
from pathlib import Path

from .model import Transaction


def load_transactions(path: str | Path) -> list[Transaction]:
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            Transaction(
                account=row["account"],
                kind=row["kind"].lower(),
                amount=float(row["amount"]),
            )
            for row in reader
        ]

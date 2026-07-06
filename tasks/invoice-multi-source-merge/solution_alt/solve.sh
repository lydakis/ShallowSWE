#!/usr/bin/env bash
set -euo pipefail

cat > invoice_merge/importer.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
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


STATUS_MAP = {
    "paid": "paid",
    "settled": "paid",
    "open": "open",
    "pending": "open",
    "draft": "open",
    "void": "void",
    "canceled": "void",
    "cancelled": "void",
}
SOURCE_RANK = {"legacy": 0, "csv": 1, "api": 2}
REJECT_RANK = {"api": 0, "csv": 1, "legacy": 2}


def norm_id(value: object) -> str:
    return str(value or "").strip().upper()


def norm_status(value: object) -> str | None:
    return STATUS_MAP.get(str(value or "").strip().lower())


def norm_date(value: object, legacy: bool = False) -> str | None:
    text = str(value or "").strip()
    if legacy:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 and text.isdigit() else None
    parts = text.split("-")
    return text if len(parts) == 3 and all(part.isdigit() for part in parts) else None


def usd_cents(amount: object, currency: object, rates: dict[str, str], legacy: bool = False) -> tuple[int | None, str | None]:
    code = str(currency or "").strip().upper()
    if code not in rates:
        return None, "unknown_currency"
    try:
        value = Decimal(str(amount))
        if legacy:
            value /= Decimal(100)
        if value <= 0:
            return None, "non_positive_amount"
        return int((value * Decimal(str(rates[code])) * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)), None
    except Exception:
        return None, "non_positive_amount"


def reject(source: str, row_ref: int, invoice_id: str, reason: str) -> dict[str, str]:
    return {"source": source, "row_ref": str(row_ref), "invoice_id": invoice_id, "reason": reason}


def add_candidate(candidates: list[dict[str, object]], rejects: list[dict[str, str]], row: dict[str, object]) -> None:
    source = str(row["source"])
    row_ref = int(row["row_ref"])
    invoice_id = norm_id(row["invoice_id"])
    status = norm_status(row["status"])
    issued = norm_date(row["issued_at"], source == "legacy")
    updated = norm_date(row["updated_at"], source == "legacy")
    amount, amount_reason = row["amount_usd_cents"]
    if not invoice_id:
        rejects.append(reject(source, row_ref, invoice_id, "missing_invoice_id"))
    elif status is None:
        rejects.append(reject(source, row_ref, invoice_id, "unknown_status"))
    elif issued is None or updated is None:
        rejects.append(reject(source, row_ref, invoice_id, "malformed_date"))
    elif amount is None:
        rejects.append(reject(source, row_ref, invoice_id, amount_reason or "non_positive_amount"))
    else:
        candidates.append(
            {
                "invoice_id": invoice_id,
                "customer": str(row["customer"]).strip(),
                "amount_usd_cents": int(amount),
                "status": status,
                "issued_at": issued,
                "updated_at": updated,
                "source": source,
                "row_ref": row_ref,
            }
        )


def import_invoices(input_dir: str | Path) -> tuple[list[Invoice], list[dict[str, str]]]:
    root = Path(input_dir)
    rates = json.loads((root / "currency_rates.json").read_text())
    candidates: list[dict[str, object]] = []
    rejects: list[dict[str, str]] = []

    for idx, item in enumerate(json.loads((root / "api_invoices.json").read_text()), 1):
        add_candidate(
            candidates,
            rejects,
            {
                "source": "api",
                "row_ref": idx,
                "invoice_id": item.get("id"),
                "customer": item.get("account", {}).get("name", ""),
                "amount_usd_cents": usd_cents(item.get("money", {}).get("value"), item.get("money", {}).get("currency"), rates),
                "status": item.get("state"),
                "issued_at": item.get("issued"),
                "updated_at": item.get("updated"),
            },
        )

    with (root / "csv_invoices.csv").open(newline="") as handle:
        for idx, item in enumerate(csv.DictReader(handle), 1):
            add_candidate(
                candidates,
                rejects,
                {
                    "source": "csv",
                    "row_ref": idx,
                    "invoice_id": item.get("invoice_id"),
                    "customer": item.get("customer", ""),
                    "amount_usd_cents": usd_cents(item.get("amount"), item.get("currency"), rates),
                    "status": item.get("status"),
                    "issued_at": item.get("issued_at"),
                    "updated_at": item.get("updated_at"),
                },
            )

    for idx, line in enumerate((root / "legacy_invoices.txt").read_text().splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("|")
        add_candidate(
            candidates,
            rejects,
            {
                "source": "legacy",
                "row_ref": idx,
                "invoice_id": parts[0] if len(parts) > 0 else "",
                "customer": parts[1] if len(parts) > 1 else "",
                "amount_usd_cents": usd_cents(parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else "", rates, legacy=True),
                "status": parts[4] if len(parts) > 4 else "",
                "issued_at": parts[5] if len(parts) > 5 else "",
                "updated_at": parts[6] if len(parts) > 6 else "",
            },
        )

    best: dict[str, dict[str, object]] = {}
    for item in candidates:
        key = str(item["invoice_id"])
        current = best.get(key)
        score = (SOURCE_RANK[str(item["source"])], str(item["updated_at"]), int(item["row_ref"]))
        if current is None or score > (SOURCE_RANK[str(current["source"])], str(current["updated_at"]), int(current["row_ref"])):
            best[key] = item

    invoices = [
        Invoice(
            str(item["invoice_id"]),
            str(item["customer"]),
            int(item["amount_usd_cents"]),
            str(item["status"]),
            str(item["issued_at"]),
            str(item["updated_at"]),
            str(item["source"]),
        )
        for item in sorted(best.values(), key=lambda row: str(row["invoice_id"]))
    ]
    rejects.sort(key=lambda row: (REJECT_RANK[row["source"]], int(row["row_ref"])))
    return invoices, rejects
PY

cat > tests/test_sources_are_merged.py <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from invoice_merge.importer import import_invoices


class SourceMergeTests(unittest.TestCase):
    def test_not_csv_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "currency_rates.json").write_text(json.dumps({"USD": "1"}))
            (root / "csv_invoices.csv").write_text(
                "invoice_id,customer,amount,currency,status,issued_at,updated_at\n"
                "INV-7,CSV,100.00,USD,open,2026-01-01,2026-01-01\n"
            )
            (root / "api_invoices.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "INV-7",
                            "account": {"name": "API"},
                            "money": {"value": "2.00", "currency": "USD"},
                            "state": "paid",
                            "issued": "2026-01-01",
                            "updated": "2026-01-03",
                        }
                    ]
                )
            )
            (root / "legacy_invoices.txt").write_text("INV-8|Legacy|300|USD|draft|20260101|20260101\n")
            invoices, _rejects = import_invoices(root)
        by_id = {invoice.invoice_id: invoice for invoice in invoices}
        self.assertEqual(by_id["INV-7"].customer, "API")
        self.assertEqual(by_id["INV-7"].amount_usd_cents, 200)
        self.assertEqual(by_id["INV-8"].amount_usd_cents, 300)


if __name__ == "__main__":
    unittest.main()
PY

#!/usr/bin/env bash
set -euo pipefail

cat > invoice_merge/importer.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
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


STATUS = {
    "paid": "paid",
    "settled": "paid",
    "open": "open",
    "pending": "open",
    "draft": "open",
    "void": "void",
    "canceled": "void",
    "cancelled": "void",
}
PRECEDENCE = {"legacy": 0, "csv": 1, "api": 2}
REJECT_ORDER = {"api": 0, "csv": 1, "legacy": 2}


def _invoice_id(value: object) -> str:
    return str(value or "").strip().upper()


def _status(value: object) -> str | None:
    return STATUS.get(str(value or "").strip().lower())


def _date(value: object, *, legacy: bool = False) -> str | None:
    text = str(value or "").strip()
    if legacy:
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
        return None
    parts = text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return text
    return None


def _cents(value: object, currency: object, rates: dict[str, str], *, legacy: bool = False) -> tuple[int | None, str | None]:
    code = str(currency or "").strip().upper()
    if code not in rates:
        return None, "unknown_currency"
    try:
        amount = Decimal(str(value))
        if legacy:
            amount /= Decimal("100")
        if amount <= 0:
            return None, "non_positive_amount"
        usd = amount * Decimal(str(rates[code]))
        return int((usd * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)), None
    except Exception:
        return None, "non_positive_amount"


def _reject(source: str, row_ref: int, invoice_id: str, reason: str) -> dict[str, str]:
    return {"source": source, "row_ref": str(row_ref), "invoice_id": invoice_id, "reason": reason}


def _validate(
    *,
    source: str,
    row_ref: int,
    invoice_id: str,
    customer: str,
    amount: int | None,
    amount_reason: str | None,
    status: str | None,
    issued_at: str | None,
    updated_at: str | None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    if not invoice_id:
        return None, _reject(source, row_ref, invoice_id, "missing_invoice_id")
    if status is None:
        return None, _reject(source, row_ref, invoice_id, "unknown_status")
    if issued_at is None or updated_at is None:
        return None, _reject(source, row_ref, invoice_id, "malformed_date")
    if amount is None:
        return None, _reject(source, row_ref, invoice_id, amount_reason or "non_positive_amount")
    return (
        {
            "invoice_id": invoice_id,
            "customer": customer.strip(),
            "amount_usd_cents": amount,
            "status": status,
            "issued_at": issued_at,
            "updated_at": updated_at,
            "source": source,
            "row_ref": row_ref,
        },
        None,
    )


def import_invoices(input_dir: str | Path) -> tuple[list[Invoice], list[dict[str, str]]]:
    root = Path(input_dir)
    rates = json.loads((root / "currency_rates.json").read_text())
    rows: list[dict[str, Any]] = []
    rejects: list[dict[str, str]] = []

    for index, item in enumerate(json.loads((root / "api_invoices.json").read_text()), start=1):
        record, reject = _validate(
            source="api",
            row_ref=index,
            invoice_id=_invoice_id(item.get("id")),
            customer=str(item.get("account", {}).get("name", "")),
            amount=(amount_info := _cents(item.get("money", {}).get("value"), item.get("money", {}).get("currency"), rates))[0],
            amount_reason=amount_info[1],
            status=_status(item.get("state")),
            issued_at=_date(item.get("issued")),
            updated_at=_date(item.get("updated")),
        )
        rows.extend([record] if record else [])
        rejects.extend([reject] if reject else [])

    with (root / "csv_invoices.csv").open(newline="") as handle:
        for index, item in enumerate(csv.DictReader(handle), start=1):
            record, reject = _validate(
                source="csv",
                row_ref=index,
                invoice_id=_invoice_id(item.get("invoice_id")),
                customer=str(item.get("customer", "")),
                amount=(amount_info := _cents(item.get("amount"), item.get("currency"), rates))[0],
                amount_reason=amount_info[1],
                status=_status(item.get("status")),
                issued_at=_date(item.get("issued_at")),
                updated_at=_date(item.get("updated_at")),
            )
            rows.extend([record] if record else [])
            rejects.extend([reject] if reject else [])

    for index, line in enumerate((root / "legacy_invoices.txt").read_text().splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("|")
        record, reject = _validate(
            source="legacy",
            row_ref=index,
            invoice_id=_invoice_id(parts[0] if len(parts) > 0 else ""),
            customer=parts[1] if len(parts) > 1 else "",
            amount=(amount_info := _cents(parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else "", rates, legacy=True))[0],
            amount_reason=amount_info[1],
            status=_status(parts[4] if len(parts) > 4 else ""),
            issued_at=_date(parts[5] if len(parts) > 5 else "", legacy=True),
            updated_at=_date(parts[6] if len(parts) > 6 else "", legacy=True),
        )
        rows.extend([record] if record else [])
        rejects.extend([reject] if reject else [])

    chosen: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = chosen.get(row["invoice_id"])
        if current is None or (
            PRECEDENCE[row["source"]],
            row["updated_at"],
            row["row_ref"],
        ) > (
            PRECEDENCE[current["source"]],
            current["updated_at"],
            current["row_ref"],
        ):
            chosen[row["invoice_id"]] = row

    invoices = [
        Invoice(
            invoice_id=row["invoice_id"],
            customer=row["customer"],
            amount_usd_cents=int(row["amount_usd_cents"]),
            status=row["status"],
            issued_at=row["issued_at"],
            updated_at=row["updated_at"],
            source=row["source"],
        )
        for row in sorted(chosen.values(), key=lambda item: item["invoice_id"])
    ]
    rejects.sort(key=lambda item: (REJECT_ORDER[item["source"]], int(item["row_ref"])))
    return invoices, rejects
PY

cat > tests/test_multi_source_import.py <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from invoice_merge.importer import import_invoices


class MultiSourceImportTests(unittest.TestCase):
    def test_api_precedence_and_legacy_source_are_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "currency_rates.json").write_text(json.dumps({"USD": "1"}))
            (root / "csv_invoices.csv").write_text(
                "invoice_id,customer,amount,currency,status,issued_at,updated_at\n"
                "INV-1,CSV,99.00,USD,open,2026-01-01,2026-01-01\n"
            )
            (root / "api_invoices.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "inv-1",
                            "account": {"name": "API"},
                            "money": {"value": "1.00", "currency": "USD"},
                            "state": "settled",
                            "issued": "2026-01-02",
                            "updated": "2026-01-02",
                        }
                    ]
                )
            )
            (root / "legacy_invoices.txt").write_text("INV-2|Legacy|250|USD|draft|20260101|20260102\n")
            invoices, rejects = import_invoices(root)
        by_id = {invoice.invoice_id: invoice for invoice in invoices}
        self.assertEqual(by_id["INV-1"].source, "api")
        self.assertEqual(by_id["INV-1"].amount_usd_cents, 100)
        self.assertEqual(by_id["INV-2"].source, "legacy")
        self.assertEqual(by_id["INV-2"].status, "open")
        self.assertEqual(rejects, [])


if __name__ == "__main__":
    unittest.main()
PY

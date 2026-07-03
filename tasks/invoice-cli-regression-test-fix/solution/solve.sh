#!/usr/bin/env bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path

path = Path("invoice_tool/importer.py")
text = path.read_text()
old = '''def import_invoices(path: str | Path) -> list[Invoice]:
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
'''
new = '''def import_invoices(path: str | Path) -> list[Invoice]:
    invoices: list[Invoice] = []
    seen_invoice_ids: set[str] = set()
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            invoice_id = row["invoice_id"].strip()
            if invoice_id in seen_invoice_ids:
                continue
            seen_invoice_ids.add(invoice_id)
            invoices.append(
                Invoice(
                    invoice_id=invoice_id,
                    customer=row["customer"].strip(),
                    amount=float(row["amount"]),
                    status=row["status"].strip().lower(),
                )
            )
    return invoices
'''
path.write_text(text.replace(old, new))
PY

cat > tests/test_duplicate_invoices.py <<'PY'
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from invoice_tool.importer import import_invoices
from invoice_tool.summary import summarize


class DuplicateInvoiceImportTests(unittest.TestCase):
    def test_duplicate_invoice_ids_are_ignored_after_first_row(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("invoice_id,customer,amount,status\n")
            handle.write("INV-1,Ada,10.00,open\n")
            handle.write("INV-1,Ada,99.00,open\n")
            handle.write("INV-2,Grace,5.00,paid\n")
            path = Path(handle.name)

        invoices = import_invoices(path)

        self.assertEqual([invoice.invoice_id for invoice in invoices], ["INV-1", "INV-2"])
        self.assertEqual(summarize(invoices)["total_amount"], 15.0)


if __name__ == "__main__":
    unittest.main()
PY

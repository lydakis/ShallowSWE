#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR"

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
    invoices_by_id: dict[str, Invoice] = {}
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            invoice_id = row["invoice_id"].strip()
            if invoice_id not in invoices_by_id:
                invoices_by_id[invoice_id] = Invoice(
                    invoice_id=invoice_id,
                    customer=row["customer"].strip(),
                    amount=float(row["amount"]),
                    status=row["status"].strip().lower(),
                )
    return list(invoices_by_id.values())
'''
if old not in text:
    raise SystemExit("expected original import_invoices implementation not found")
path.write_text(text.replace(old, new, 1))
PY

cat > tests/test_duplicate_invoice_cli.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DuplicateInvoiceCliTests(unittest.TestCase):
    def test_cli_summarizes_first_occurrence_of_duplicate_invoice(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("invoice_id,customer,amount,status\n")
            handle.write("INV-1,Ada,10.00,open\n")
            handle.write("INV-1,Ada,999.00,open\n")
            handle.write("INV-2,Grace,5.50,paid\n")
            csv_path = Path(handle.name)

        result = subprocess.run(
            [sys.executable, "-m", "invoice_tool.cli", str(csv_path)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertIn("invoices: 2", result.stdout)
        self.assertIn("total: $15.50", result.stdout)
        self.assertIn("open: $10.00", result.stdout)


if __name__ == "__main__":
    unittest.main()
PY

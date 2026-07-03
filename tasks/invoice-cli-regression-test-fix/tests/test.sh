#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from pathlib import Path
import csv
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "/app")

from invoice_tool.importer import import_invoices
from invoice_tool.summary import summarize


class HiddenInvoiceBehaviorTests(unittest.TestCase):
    def make_csv(self) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
        writer = csv.writer(handle)
        writer.writerow(["invoice_id", "customer", "amount", "status"])
        writer.writerow(["INV-200", "Mae Jemison", "10.00", "open"])
        writer.writerow(["INV-201", "Dorothy Vaughan", "7.50", "paid"])
        writer.writerow(["INV-200", "Mae Jemison", "999.99", "open"])
        handle.close()
        return Path(handle.name)

    def test_duplicate_invoice_ids_keep_first_occurrence(self) -> None:
        invoices = import_invoices(self.make_csv())

        self.assertEqual([invoice.invoice_id for invoice in invoices], ["INV-200", "INV-201"])
        self.assertEqual(
            summarize(invoices),
            {
                "invoice_count": 2,
                "total_amount": 17.50,
                "open_amount": 10.00,
            },
        )

    def test_cli_uses_deduplicated_import(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "invoice_tool.cli", str(self.make_csv())],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertIn("invoices: 2", result.stdout)
        self.assertIn("total: $17.50", result.stdout)

    def test_agent_added_duplicate_regression_test(self) -> None:
        test_files = list(Path("/app/tests").glob("test*.py"))
        combined = "\n".join(path.read_text() for path in test_files)

        self.assertIn("duplicate", combined.lower())
        self.assertIn("invoice", combined.lower())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenInvoiceBehaviorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"

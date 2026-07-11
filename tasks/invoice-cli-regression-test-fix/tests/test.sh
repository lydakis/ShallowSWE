#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

APP_ROOT = Path(os.environ.get("APP_DIR", "/app"))
LOG_DIR = Path(os.environ.get("LOG_DIR", "/logs/verifier"))

sys.path.insert(0, str(APP_ROOT))

from invoice_tool.importer import import_invoices
from invoice_tool.summary import summarize


class HiddenInvoiceBehaviorTests(unittest.TestCase):
    def make_csv(self) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
        writer = csv.writer(handle)
        writer.writerow(["invoice_id", "customer", "amount", "status"])
        writer.writerow([" INV-200 ", "Mae Jemison", "10.00", "open"])
        writer.writerow(["INV-201", "Dorothy Vaughan", "7.50", "paid"])
        writer.writerow(["INV-200", "Mae Jemison", "999.99", "open"])
        handle.close()
        return Path(handle.name)

    def test_duplicate_invoice_ids_keep_first_occurrence(self) -> None:
        invoices = import_invoices(self.make_csv())

        self.assertEqual([invoice.invoice_id for invoice in invoices], ["INV-200", "INV-201"])
        self.assertEqual(invoices[0].customer, "Mae Jemison")
        self.assertEqual(invoices[0].amount, 10.00)
        self.assertEqual(
            summarize(invoices),
            {
                "invoice_count": 2,
                "total_amount": 17.50,
                "open_amount": 10.00,
            },
        )

    def test_cli_uses_deduplicated_import(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(APP_ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "invoice_tool.cli", str(self.make_csv())],
            cwd=APP_ROOT,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["invoices: 2", "total: $17.50", "open: $10.00"],
        )

    def test_agent_added_duplicate_regression_test(self) -> None:
        def run_visible_tests(app_root: Path) -> subprocess.CompletedProcess[str]:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(app_root)
            return subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=app_root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        fixed_result = run_visible_tests(APP_ROOT)
        self.assertEqual(
            fixed_result.returncode,
            0,
            fixed_result.stdout + fixed_result.stderr,
        )

        with tempfile.TemporaryDirectory() as tmp:
            mutant_app = Path(tmp) / "app"
            shutil.copytree(
                APP_ROOT,
                mutant_app,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            (mutant_app / "invoice_tool" / "importer.py").write_text(
                '''from __future__ import annotations

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
'''
            )

            mutant_result = run_visible_tests(mutant_app)

        self.assertNotEqual(
            mutant_result.returncode,
            0,
            "visible tests still pass when duplicate-import bug is restored",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenInvoiceBehaviorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

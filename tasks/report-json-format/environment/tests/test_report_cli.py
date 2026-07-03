from __future__ import annotations

import subprocess
import sys
import unittest

from account_report.loader import load_transactions
from account_report.report import build_report
from account_report.serializers import render_report


class ReportCliTests(unittest.TestCase):
    def test_builds_summary(self) -> None:
        report = build_report(load_transactions("/app/transactions.csv"))

        self.assertEqual(report["account"], "ops-checking")
        self.assertEqual(report["transaction_count"], 4)
        self.assertEqual(report["total_debits"], 200.0)
        self.assertEqual(report["total_credits"], 1600.0)
        self.assertEqual(report["net_change"], 1400.0)

    def test_csv_output_still_works(self) -> None:
        report = build_report(load_transactions("/app/transactions.csv"))

        self.assertEqual(
            render_report(report, "csv"),
            "account,transaction_count,total_debits,total_credits,net_change\n"
            "ops-checking,4,200.00,1600.00,1400.00",
        )

    def test_cli_text_output_still_works(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "account_report.cli", "/app/transactions.csv"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertIn("Account: ops-checking", result.stdout)
        self.assertIn("Net change: $1400.00", result.stdout)


if __name__ == "__main__":
    unittest.main()

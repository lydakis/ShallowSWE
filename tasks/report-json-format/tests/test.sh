#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from pathlib import Path
import json
import subprocess
import sys
import unittest

sys.path.insert(0, "/app")

from account_report.loader import load_transactions
from account_report.report import build_report
from account_report.serializers import render_report


EXPECTED = {
    "account": "ops-checking",
    "transaction_count": 4,
    "total_debits": 200.0,
    "total_credits": 1600.0,
    "net_change": 1400.0,
}


class HiddenJsonFormatTests(unittest.TestCase):
    def test_serializer_supports_json_format(self) -> None:
        rendered = render_report(build_report(load_transactions("/app/transactions.csv")), "json")

        self.assertEqual(json.loads(rendered), EXPECTED)

    def test_cli_accepts_json_choice(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "account_report.cli",
                "/app/transactions.csv",
                "--format",
                "json",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertEqual(json.loads(result.stdout), EXPECTED)

    def test_existing_formats_are_unchanged(self) -> None:
        csv_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "account_report.cli",
                "/app/transactions.csv",
                "--format",
                "csv",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertIn("ops-checking,4,200.00,1600.00,1400.00", csv_result.stdout)

    def test_help_mentions_json_format(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "account_report.cli", "--help"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertIn("json", result.stdout)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenJsonFormatTests)
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

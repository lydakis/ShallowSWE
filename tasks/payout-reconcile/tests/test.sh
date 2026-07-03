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


EXPECTED_PAYOUTS = [
    {
        "customer_id": "C-100",
        "customer_name": "Ada Lovelace",
        "invoice_id": "INV-100",
        "paid_amount": "120.00",
        "refund_amount": "20.00",
        "net_amount": "100.00",
    },
    {
        "customer_id": "C-101",
        "customer_name": "Grace Hopper",
        "invoice_id": "INV-101",
        "paid_amount": "85.50",
        "refund_amount": "0.00",
        "net_amount": "85.50",
    },
]
EXPECTED_REJECTS = [
    {"source": "invoice", "record_id": "INV-102", "reason": "unknown_customer"},
    {"source": "payment", "record_id": "PAY-4", "reason": "unknown_invoice"},
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


class HiddenPayoutReconcileTests(unittest.TestCase):
    def test_cli_writes_exact_reconciliation_outputs(self) -> None:
        output_dir = Path(tempfile.mkdtemp())
        subprocess.run(
            [
                sys.executable,
                "-m",
                "payout_reconcile.cli",
                "--input-dir",
                "/app/data",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
        )

        self.assertEqual(read_csv(output_dir / "payouts.csv"), EXPECTED_PAYOUTS)
        self.assertEqual(read_csv(output_dir / "rejects.csv"), EXPECTED_REJECTS)

    def test_outputs_are_sorted_and_have_expected_headers(self) -> None:
        output_dir = Path(tempfile.mkdtemp())
        subprocess.run(
            [
                sys.executable,
                "-m",
                "payout_reconcile.cli",
                "--input-dir",
                "/app/data",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
        )

        payout_lines = (output_dir / "payouts.csv").read_text().splitlines()
        reject_lines = (output_dir / "rejects.csv").read_text().splitlines()

        self.assertEqual(
            payout_lines[0],
            "customer_id,customer_name,invoice_id,paid_amount,refund_amount,net_amount",
        )
        self.assertEqual(reject_lines[0], "source,record_id,reason")
        self.assertEqual(
            [row["invoice_id"] for row in read_csv(output_dir / "payouts.csv")],
            ["INV-100", "INV-101"],
        )
        self.assertEqual(
            [(row["source"], row["record_id"]) for row in read_csv(output_dir / "rejects.csv")],
            [("invoice", "INV-102"), ("payment", "PAY-4")],
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenPayoutReconcileTests)
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

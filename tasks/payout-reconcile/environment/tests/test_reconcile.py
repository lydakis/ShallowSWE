from __future__ import annotations

from pathlib import Path
import csv
import tempfile
import unittest

from payout_reconcile.reconcile import reconcile


class ReconcileTests(unittest.TestCase):
    def test_writes_report_files(self) -> None:
        output_dir = Path(tempfile.mkdtemp())

        reconcile("/app/data", output_dir)

        self.assertTrue((output_dir / "payouts.csv").exists())
        self.assertTrue((output_dir / "rejects.csv").exists())

    def test_rejects_unknown_payment_invoice(self) -> None:
        output_dir = Path(tempfile.mkdtemp())
        reconcile("/app/data", output_dir)

        with (output_dir / "rejects.csv").open(newline="") as handle:
            rejects = list(csv.DictReader(handle))

        self.assertIn(
            {
                "source": "payment",
                "record_id": "PAY-4",
                "reason": "unknown_invoice",
            },
            rejects,
        )


if __name__ == "__main__":
    unittest.main()

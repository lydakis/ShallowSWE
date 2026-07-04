from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from fulfillment_status.importer import import_orders_csv
from fulfillment_status.report import build_report
from fulfillment_status.statuses import StatusError, is_terminal_status, normalize_status
from fulfillment_status.webhook import apply_carrier_webhook


class ExistingStatusTests(unittest.TestCase):
    def test_existing_aliases_and_terminal_statuses_still_work(self) -> None:
        self.assertEqual(normalize_status("canceled"), "cancelled")
        self.assertEqual(normalize_status("lost_in_transit"), "lost")
        self.assertTrue(is_terminal_status("delivered"))
        self.assertTrue(is_terminal_status("cancelled"))
        self.assertTrue(is_terminal_status("lost"))
        self.assertFalse(is_terminal_status("hold"))
        self.assertFalse(is_terminal_status("pending_review"))

    def test_import_csv_existing_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "orders.csv"
            csv_path.write_text(
                "order_id,status,customer\n"
                "ORD-1,canceled,Ada\n"
                "ORD-2,hold,Linus\n"
            )

            orders = import_orders_csv(csv_path)

        self.assertEqual([order["status"] for order in orders], ["cancelled", "hold"])

    def test_webhook_existing_status_and_report_shape(self) -> None:
        orders = [{"order_id": "ORD-1", "status": "shipped", "customer": "Ada"}]
        updated = apply_carrier_webhook(
            orders,
            {"order_id": "ORD-1", "carrier_status": "lost_in_transit"},
        )
        report = build_report(updated)

        self.assertEqual(updated[0]["status"], "lost")
        self.assertEqual(report["terminal"], 1)
        self.assertEqual(report["successful"], 0)
        self.assertEqual(report["terminal_order_ids"], ["ORD-1"])

    def test_unknown_status_still_rejected(self) -> None:
        with self.assertRaises(StatusError):
            normalize_status("anything_goes")

    def test_repair_cli_preserves_output_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orders_path = Path(tmp) / "orders.json"
            output_path = Path(tmp) / "out.json"
            orders_path.write_text(
                json.dumps([{"order_id": "ORD-1", "status": "shipped", "customer": "Ada"}])
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "fulfillment_status.cli",
                    "repair",
                    "--orders",
                    str(orders_path),
                    "--order-id",
                    "ORD-1",
                    "--status",
                    "hold",
                    "--output-json",
                    str(output_path),
                ],
                check=True,
            )

            orders = json.loads(output_path.read_text())

        self.assertEqual(orders, [{"customer": "Ada", "order_id": "ORD-1", "status": "hold"}])


if __name__ == "__main__":
    unittest.main()

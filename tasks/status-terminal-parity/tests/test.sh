#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "/app")

from fulfillment_status.importer import import_orders_csv
from fulfillment_status.report import build_report
from fulfillment_status.statuses import StatusError, is_successful_status, is_terminal_status, normalize_status
from fulfillment_status.webhook import apply_carrier_webhook


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "fulfillment_status.cli", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class HiddenTerminalParityTests(unittest.TestCase):
    def test_status_helper_accepts_new_status_and_alias(self) -> None:
        self.assertEqual(normalize_status("return_to_sender"), "return_to_sender")
        self.assertEqual(normalize_status("RTS"), "return_to_sender")
        self.assertTrue(is_terminal_status("return_to_sender"))
        self.assertTrue(is_terminal_status("rts"))
        self.assertFalse(is_successful_status("return_to_sender"))
        self.assertFalse(is_successful_status("rts"))

    def test_csv_import_canonicalizes_new_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "orders.csv"
            csv_path.write_text(
                "order_id,status,customer\n"
                "ORD-200,rts,Ada\n"
                "ORD-201,return_to_sender,Grace\n"
                "ORD-202,canceled,Linus\n"
            )

            orders = import_orders_csv(csv_path)
            report = build_report(orders)

        self.assertEqual(
            [order["status"] for order in orders],
            ["return_to_sender", "return_to_sender", "cancelled"],
        )
        self.assertEqual(report["terminal"], 3)
        self.assertEqual(report["successful"], 0)
        self.assertEqual(report["by_status"]["return_to_sender"], 2)

    def test_webhook_and_report_share_terminal_semantics(self) -> None:
        orders = [
            {"order_id": "ORD-100", "status": "shipped", "customer": "Ada"},
            {"order_id": "ORD-101", "status": "delivered", "customer": "Grace"},
            {"order_id": "ORD-102", "status": "pending_review", "customer": "Linus"},
        ]

        updated = apply_carrier_webhook(
            orders,
            {"order_id": "ORD-100", "carrier_status": "rts"},
        )
        report = build_report(updated)

        self.assertEqual(updated[0]["status"], "return_to_sender")
        self.assertEqual(report["terminal"], 2)
        self.assertEqual(report["successful"], 1)
        self.assertEqual(report["open"], 1)
        self.assertEqual(report["terminal_order_ids"], ["ORD-100", "ORD-101"])
        self.assertEqual(report["successful_order_ids"], ["ORD-101"])

    def test_admin_repair_cli_accepts_literal_and_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orders_path = root / "orders.json"
            first_path = root / "first.json"
            second_path = root / "second.json"
            report_path = root / "report.json"
            orders_path.write_text(
                json.dumps(
                    [
                        {"order_id": "ORD-300", "status": "shipped", "customer": "Ada"},
                        {"order_id": "ORD-301", "status": "hold", "customer": "Grace"},
                    ]
                )
            )

            run_cli(
                [
                    "repair",
                    "--orders",
                    str(orders_path),
                    "--order-id",
                    "ORD-300",
                    "--status",
                    "rts",
                    "--output-json",
                    str(first_path),
                ]
            )
            run_cli(
                [
                    "repair",
                    "--orders",
                    str(first_path),
                    "--order-id",
                    "ORD-301",
                    "--status",
                    "return_to_sender",
                    "--output-json",
                    str(second_path),
                ]
            )
            run_cli(["report", "--orders", str(second_path), "--output-json", str(report_path)])

            orders = json.loads(second_path.read_text())
            report = json.loads(report_path.read_text())

        self.assertEqual([order["status"] for order in orders], ["return_to_sender", "return_to_sender"])
        self.assertEqual(report["terminal"], 2)
        self.assertEqual(report["successful"], 0)
        self.assertEqual(report["open"], 0)

    def test_help_mentions_new_status_and_alias(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "fulfillment_status.cli", "repair", "--help"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertIn("return_to_sender", result.stdout)
        self.assertIn("rts", result.stdout)

    def test_unknown_statuses_are_not_silently_accepted(self) -> None:
        with self.assertRaises(StatusError):
            normalize_status("returned")

        with tempfile.TemporaryDirectory() as tmp:
            orders_path = Path(tmp) / "orders.json"
            output_path = Path(tmp) / "out.json"
            orders_path.write_text(
                json.dumps([{"order_id": "ORD-1", "status": "shipped", "customer": "Ada"}])
            )
            result = subprocess.run(
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
                    "returned",
                    "--output-json",
                    str(output_path),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenTerminalParityTests)
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

from __future__ import annotations

from pathlib import Path
import csv
import json
import os
import tempfile
import unittest

from ledger_migrator.migrate import migrate


APP_DIR = Path(os.environ.get("APP_DIR", "/app"))


class ExistingMigrationTests(unittest.TestCase):
    def test_v1_only_migration_still_writes_v3_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            migrate(APP_DIR / "fixtures" / "v1", output)

            with (output / "ledger.csv").open(newline="") as handle:
                ledger = list(csv.DictReader(handle))
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(ledger[0]["amount_cents"], "20")
        self.assertEqual(summary["usage_events"], 1)
        self.assertEqual(summary["net_cents"], 20)

    def test_v2_only_migration_uses_event_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            migrate(APP_DIR / "fixtures" / "v2", output)

            normalized = [
                json.loads(line)
                for line in (output / "normalized_events.jsonl").read_text().splitlines()
            ]
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(normalized[0]["plan_id"], "pro")
        self.assertEqual(normalized[0]["gross_cents"], 75)
        self.assertEqual(summary["gross_cents"], 75)

    def test_v4_fixture_writes_evidence_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            migrate(APP_DIR / "fixtures" / "v4", output)

            normalized = [
                json.loads(line)
                for line in (output / "normalized_events.jsonl").read_text().splitlines()
            ]
            with (output / "account_balances.csv").open(newline="") as handle:
                balances = list(csv.DictReader(handle))
            with (output / "plan_revenue.csv").open(newline="") as handle:
                plan_revenue = list(csv.DictReader(handle))
            audit = json.loads((output / "migration_audit.json").read_text())

        self.assertEqual(normalized[0]["recognition_month"], "2026-01")
        self.assertIn("usd_net_micros", normalized[0])
        self.assertEqual(
            list(balances[0]),
            [
                "account_id",
                "region",
                "segment",
                "currency",
                "ending_balance_cents",
                "ending_balance_usd_micros",
                "status",
            ],
        )
        self.assertEqual(
            list(plan_revenue[0]),
            [
                "recognition_month",
                "plan_id",
                "currency",
                "gross_cents",
                "discount_cents",
                "tax_cents",
                "net_cents",
                "net_usd_micros",
            ],
        )
        self.assertEqual(audit["schema_version"], "v4")
        self.assertEqual(audit["generated_at"], "deterministic")


if __name__ == "__main__":
    unittest.main()

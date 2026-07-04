from __future__ import annotations

from pathlib import Path
import csv
import json
import tempfile
import unittest

from ledger_migrator.migrate import migrate


class ExistingMigrationTests(unittest.TestCase):
    def test_v1_only_migration_still_writes_v3_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            migrate("/app/fixtures/v1", output)

            with (output / "ledger.csv").open(newline="") as handle:
                ledger = list(csv.DictReader(handle))
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(ledger[0]["amount_cents"], "20")
        self.assertEqual(summary["usage_events"], 1)
        self.assertEqual(summary["net_cents"], 20)

    def test_v2_only_migration_uses_event_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            migrate("/app/fixtures/v2", output)

            normalized = [
                json.loads(line)
                for line in (output / "normalized_events.jsonl").read_text().splitlines()
            ]
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(normalized[0]["plan_id"], "pro")
        self.assertEqual(normalized[0]["gross_cents"], 75)
        self.assertEqual(summary["gross_cents"], 75)


if __name__ == "__main__":
    unittest.main()

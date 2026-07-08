#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

app = Path(os.environ.get("APP_DIR", "/app"))


def run(root: Path) -> None:
    script = root / "scripts" / "build_schedule.py"
    assert script.exists(), "missing scripts/build_schedule.py"
    subprocess.run([sys.executable, str(script)], cwd=root, check=True)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


class BillingProrationScheduleTests(unittest.TestCase):
    def test_visible_schedule(self) -> None:
        run(app)
        self.assertEqual(
            rows(app / "output" / "schedule.csv"),
            [
                {
                    "account_id": "acct-1",
                    "event_id": "e-100",
                    "action": "upgrade",
                    "effective_start": "2026-07-11",
                    "effective_end": "2026-08-01",
                    "period_days": "31",
                    "remaining_days": "21",
                    "amount_usd_cents": "6774",
                },
                {
                    "account_id": "acct-2",
                    "event_id": "e-200",
                    "action": "downgrade",
                    "effective_start": "2026-02-16",
                    "effective_end": "2026-03-01",
                    "period_days": "28",
                    "remaining_days": "13",
                    "amount_usd_cents": "-8357",
                },
                {
                    "account_id": "acct-3",
                    "event_id": "e-300",
                    "action": "cancel",
                    "effective_start": "2026-04-20",
                    "effective_end": "2026-05-01",
                    "period_days": "30",
                    "remaining_days": "11",
                    "amount_usd_cents": "-5500",
                },
                {
                    "account_id": "acct-4",
                    "event_id": "e-400",
                    "action": "upgrade",
                    "effective_start": "2026-05-31",
                    "effective_end": "2026-06-01",
                    "period_days": "31",
                    "remaining_days": "1",
                    "amount_usd_cents": "97",
                },
            ],
        )
        self.assertEqual(
            json.loads((app / "output" / "summary.json").read_text()),
            {
                "event_count": 5,
                "line_item_count": 4,
                "net_total_cents": -6986,
                "total_charge_cents": 6871,
                "total_credit_cents": 13857,
            },
        )

    def test_hidden_leap_boundary_and_cancel_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            (root / "scripts").mkdir(parents=True)
            (root / "input").mkdir()
            shutil.copy2(app / "scripts" / "build_schedule.py", root / "scripts" / "build_schedule.py")
            (root / "input" / "subscription_events.csv").write_text(
                "account_id,event_id,event_date,period_start,period_end,old_plan,new_plan,old_monthly_cents,new_monthly_cents\n"
                "acct-z,e-1,2024-02-15,2024-02-01,2024-03-01,basic,pro,1000,2000\n"
                "acct-z,e-2,2024-02-29,2024-02-01,2024-03-01,pro,cancelled,2000,999999\n"
            )
            run(root)
            hidden_rows = rows(root / "output" / "schedule.csv")

        self.assertEqual(hidden_rows[0]["period_days"], "29")
        self.assertEqual(hidden_rows[0]["remaining_days"], "15")
        self.assertEqual(hidden_rows[0]["amount_usd_cents"], "517")
        self.assertEqual(hidden_rows[1]["amount_usd_cents"], "-69")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(BillingProrationScheduleTests)
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

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
sys.path.insert(0, str(app))

from retry_parser.scheduler import build_retry_plan


def run_cli(root: Path, csv_path: Path) -> list[dict[str, object]]:
    result = subprocess.run(
        [sys.executable, "-m", "retry_parser.cli", str(csv_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines()]


class RetryPolicyMigrationTests(unittest.TestCase):
    def test_visible_rows(self) -> None:
        rows = run_cli(app, app / "retries.csv")
        self.assertEqual(
            rows[0],
            {
                "attempts": 0,
                "delay_seconds": 10,
                "job_id": "job-a",
                "max_attempts": 3,
                "mode": "standard",
                "retry_schedule_seconds": [10, 20, 40],
            },
        )
        self.assertEqual(rows[1]["retry_schedule_seconds"], [30, 60])
        self.assertEqual(set(rows[2]), {"job_id", "attempts", "delay_seconds", "mode"})
        self.assertEqual(rows[2]["mode"], "manual")
        self.assertEqual(set(rows[3]), {"job_id", "attempts", "delay_seconds", "mode"})
        self.assertEqual(set(rows[4]), {"job_id", "attempts", "delay_seconds", "mode"})
        self.assertEqual(
            rows[5],
            {"job_id": "job-f", "attempts": 0, "delay_seconds": 30, "mode": "fallback"},
        )

    def test_hidden_backoff_boundaries(self) -> None:
        row = {
            "job_id": "cap",
            "attempts": "1",
            "delay_seconds": "1200",
            "max_attempts": "5",
            "retryable": "1",
            "status": "failed",
            "mode": "",
        }
        self.assertEqual(
            build_retry_plan(row),
            {
                "job_id": "cap",
                "attempts": 1,
                "delay_seconds": 1200,
                "max_attempts": 5,
                "mode": "standard",
                "retry_schedule_seconds": [1200, 2400, 3600, 3600],
            },
        )

    def test_hidden_cli_uses_code_not_visible_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(app / "retry_parser", root / "retry_parser")
            csv_path = root / "hidden.csv"
            csv_path.write_text(
                "job_id,attempts,delay_seconds,max_attempts,retryable,status,mode\n"
                "h-1,2,7,5,TRUE,failed,fast\n"
                "h-2,0,9,2,no,failed,manual\n"
            )
            rows = run_cli(root, csv_path)

        self.assertEqual(rows[0]["retry_schedule_seconds"], [7, 14, 28])
        self.assertEqual(set(rows[1]), {"job_id", "attempts", "delay_seconds", "mode"})


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RetryPolicyMigrationTests)
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

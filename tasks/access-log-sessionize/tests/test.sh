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


def run(root: Path) -> None:
    script = root / "scripts" / "sessionize.py"
    assert script.exists(), "missing scripts/sessionize.py"
    subprocess.run([sys.executable, str(script)], cwd=root, check=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


class AccessLogSessionizeTests(unittest.TestCase):
    def test_visible_fixture(self) -> None:
        run(app)
        self.assertEqual(
            read_csv(app / "output" / "sessions.csv"),
            [
                {
                    "session_id": "S-c-1-001",
                    "client_id": "c-1",
                    "started_at": "2026-07-04T23:50:00Z",
                    "ended_at": "2026-07-05T00:05:00Z",
                    "event_count": "3",
                    "duration_seconds": "900",
                    "status_max": "500",
                    "first_request_id": "req-1",
                    "last_request_id": "req-3",
                },
                {
                    "session_id": "S-c-1-002",
                    "client_id": "c-1",
                    "started_at": "2026-07-05T00:21:00Z",
                    "ended_at": "2026-07-05T00:21:00Z",
                    "event_count": "1",
                    "duration_seconds": "0",
                    "status_max": "200",
                    "first_request_id": "req-4",
                    "last_request_id": "req-4",
                },
                {
                    "session_id": "S-c-2-001",
                    "client_id": "c-2",
                    "started_at": "2026-07-04T23:55:00Z",
                    "ended_at": "2026-07-05T00:10:00Z",
                    "event_count": "2",
                    "duration_seconds": "900",
                    "status_max": "429",
                    "first_request_id": "req-2",
                    "last_request_id": "req-5",
                },
                {
                    "session_id": "S-c-2-002",
                    "client_id": "c-2",
                    "started_at": "2026-07-05T00:26:01Z",
                    "ended_at": "2026-07-05T00:26:01Z",
                    "event_count": "1",
                    "duration_seconds": "0",
                    "status_max": "200",
                    "first_request_id": "req-6",
                    "last_request_id": "req-6",
                },
            ],
        )
        self.assertEqual(
            json.loads((app / "output" / "summary.json").read_text()),
            {"client_count": 2, "event_count": 7, "rejected_count": 1, "session_count": 4},
        )
        self.assertEqual(
            read_csv(app / "output" / "rejects.csv"),
            [{"file": "api.log", "line": "3", "reason": "malformed_line"}],
        )

    def test_hidden_boundary_and_sorting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            (root / "scripts").mkdir(parents=True)
            (root / "input").mkdir()
            shutil.copy2(app / "scripts" / "sessionize.py", root / "scripts" / "sessionize.py")
            (root / "input" / "b.log").write_text(
                "2026-07-06T10:45:01Z u-1 GET /late 503 h-4\n"
                "2026-07-06T10:00:00Z u-1 GET /start 200 h-1\n"
            )
            (root / "input" / "a.log").write_text(
                "2026-07-06T10:15:00Z u-1 GET /exact 201 h-2\n"
                "2026-07-06T10:30:00Z u-1 POST /still 202 h-3\n"
                "2026-07-06T10:01:00Z u-2 GET /solo 200 h-5\n"
            )
            run(root)
            rows = read_csv(root / "output" / "sessions.csv")

        self.assertEqual([row["session_id"] for row in rows], ["S-u-1-001", "S-u-1-002", "S-u-2-001"])
        self.assertEqual(rows[0]["event_count"], "3")
        self.assertEqual(rows[0]["duration_seconds"], "1800")
        self.assertEqual(rows[1]["first_request_id"], "h-4")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AccessLogSessionizeTests)
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

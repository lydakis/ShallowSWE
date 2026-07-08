#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

app = Path(os.environ.get("APP_DIR", "/app"))
sys.path.insert(0, str(app))

from notifier.renderer import render_event


def run_cli(root: Path, events: Path) -> list[dict[str, str]]:
    result = subprocess.run(
        [sys.executable, "-m", "notifier.cli", str(events)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines()]


class NotificationLocaleFallbackTests(unittest.TestCase):
    def test_visible_events(self) -> None:
        rows = run_cli(app, app / "events.json")
        self.assertEqual(rows[0]["body"], "Welcome, Ada!")
        self.assertEqual(rows[1]["body"], "Servus, Bert!")
        self.assertEqual(rows[2]["body"], "Hallo Clara, Rechnung INV-9 ist bereit.")
        self.assertEqual(rows[3]["body"], "Hi Dana &amp; Co, invoice &lt;INV-10&gt; is ready.")
        self.assertEqual(rows[4]["body"], "Thanks for using LedgerKit.")

    def test_hidden_base_language_and_missing_vars(self) -> None:
        self.assertEqual(
            render_event(
                {
                    "id": "h-1",
                    "locale": "de-CH",
                    "template": "invoice_ready",
                    "vars": {"name": "Eva", "invoice_id": "R-1"},
                }
            ),
            {"id": "h-1", "locale": "de-CH", "body": "Hallo Eva, Rechnung R-1 ist bereit."},
        )
        self.assertEqual(
            render_event({"id": "h-2", "locale": "es-MX", "template": "welcome", "vars": {}}),
            {"id": "h-2", "locale": "es-MX", "body": "Welcome, !"},
        )

    def test_hidden_cli_uses_catalogs_not_fixture_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(app / "notifier", root / "notifier")
            events = root / "hidden.json"
            events.write_text(
                json.dumps(
                    [
                        {
                            "id": "h-3",
                            "locale": "de-AT",
                            "template": "invoice_ready",
                            "vars": {"name": "<Zoe>", "invoice_id": "A&B"},
                        }
                    ]
                )
            )
            rows = run_cli(root, events)

        self.assertEqual(rows[0]["body"], "Hallo &lt;Zoe&gt;, Rechnung A&amp;B ist bereit.")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(NotificationLocaleFallbackTests)
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

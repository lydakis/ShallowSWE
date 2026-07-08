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

VISIBLE_TICKETS = [
    {"id": "T-100", "title": "Auth outage", "severity": "critical", "type": "bug", "product_area": "auth", "priority": "P2", "owner": "platform", "labels": []},
    {"id": "T-101", "title": "Checkout timeout", "severity": "high", "type": "bug", "product_area": "checkout", "priority": "P2", "owner": "platform", "labels": ["payments"]},
    {"id": "T-102", "title": "Docs typo", "severity": "low", "type": "docs", "product_area": "docs", "priority": "P3", "owner": "support", "labels": ["triaged"]},
    {"id": "T-103", "title": "Invoice copy", "severity": "medium", "type": "bug", "product_area": "billing", "priority": "P1", "owner": "payments", "labels": ["triaged"]},
    {"id": "T-104", "title": "Worker warning", "severity": "medium", "type": "bug", "product_area": "platform", "priority": "P2", "owner": "platform", "labels": ["triaged"]},
    {"id": "T-105", "title": "Guide screenshot stale", "severity": "low", "type": "docs", "product_area": "docs", "priority": "P2", "owner": "platform", "labels": []},
    {"id": "T-106", "title": "Search index lag", "severity": "high", "type": "bug", "product_area": "search", "priority": "P1", "owner": "platform", "labels": ["triaged"]},
    {"id": "T-107", "title": "Card retry loop", "severity": "medium", "type": "bug", "product_area": "checkout", "priority": "P3", "owner": "support", "labels": []},
    {"id": "T-108", "title": "Receipt wording", "severity": "low", "type": "bug", "product_area": "billing", "priority": "P2", "owner": "payments", "labels": ["billing"]},
    {"id": "T-109", "title": "Token exposure report", "severity": "high", "type": "bug", "product_area": "auth", "priority": "P1", "owner": "platform", "labels": ["security"]},
    {"id": "T-110", "title": "API docs missing enum", "severity": "medium", "type": "docs", "product_area": "docs", "priority": "P2", "owner": "support", "labels": []},
    {"id": "T-111", "title": "Coupon banner broken", "severity": "low", "type": "bug", "product_area": "checkout", "priority": "P3", "owner": "payments", "labels": []},
    {"id": "T-112", "title": "Release note typo", "severity": "low", "type": "docs", "product_area": "docs", "priority": "P3", "owner": "support", "labels": ["docs", "triaged"]},
    {"id": "T-113", "title": "Queue dashboard slow", "severity": "medium", "type": "bug", "product_area": "platform", "priority": "P2", "owner": "platform", "labels": ["triaged"]},
]


def desired(ticket: dict[str, object]) -> dict[str, object]:
    labels = sorted({str(label) for label in ticket.get("labels", []) if str(label)} | {"triaged"})
    severity = str(ticket.get("severity", ""))
    product = str(ticket.get("product_area", ""))
    ticket_type = str(ticket.get("type", ""))
    if severity == "critical" or "security" in labels:
        priority = "P0"
    elif severity == "high" or product in {"checkout", "billing"}:
        priority = "P1"
    elif severity == "low" or ticket_type == "docs":
        priority = "P3"
    else:
        priority = "P2"
    if "security" in labels:
        owner = "security"
    elif product in {"checkout", "billing"}:
        owner = "payments"
    elif ticket_type == "docs":
        owner = "support"
    else:
        owner = "platform"
    updated = dict(ticket)
    updated["priority"] = priority
    updated["owner"] = owner
    updated["labels"] = labels
    return updated


def expected_call(ticket: dict[str, object]) -> str:
    labels = ",".join(str(label) for label in ticket["labels"])
    return f"update_ticket {ticket['id']} priority={ticket['priority']} owner={ticket['owner']} labels={labels}"


def run(root: Path) -> None:
    script = root / "scripts" / "apply_task.py"
    assert script.exists(), "missing scripts/apply_task.py"
    subprocess.run([sys.executable, str(script)], cwd=root, check=True)


def read_tickets(root: Path) -> list[dict[str, object]]:
    return json.loads((root / "api_state" / "tickets.json").read_text())


class TicketBulkTriageTests(unittest.TestCase):
    def assert_reconciled(self, root: Path, original: list[dict[str, object]]) -> None:
        before_by_id = {ticket["id"]: ticket for ticket in original}
        after = read_tickets(root)
        after_by_id = {ticket["id"]: ticket for ticket in after}
        self.assertEqual(set(after_by_id), set(before_by_id))
        self.assertEqual(len(after), len(original))

        expected_after = [desired(ticket) for ticket in original]
        self.assertEqual(after, expected_after)

        changed = [
            ticket
            for ticket, expected in zip(original, expected_after, strict=True)
            if any(ticket.get(key) != expected.get(key) for key in ("priority", "owner", "labels"))
        ]
        expected_calls = [expected_call(desired(ticket)) for ticket in sorted(changed, key=lambda row: row["id"])]
        calls_text = (root / "api_state" / "calls.log").read_text()
        actual_calls = calls_text.splitlines()
        self.assertEqual(actual_calls, expected_calls)

    def test_visible_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            (root / "scripts").mkdir(parents=True)
            (root / "api_state").mkdir()
            shutil.copy2(app / "scripts" / "apply_task.py", root / "scripts" / "apply_task.py")
            (root / "api_state" / "tickets.json").write_text(json.dumps(VISIBLE_TICKETS, indent=2))
            (root / "api_state" / "calls.log").write_text("")
            run(root)
            self.assert_reconciled(root, VISIBLE_TICKETS)
            calls = (root / "api_state" / "calls.log").read_text().splitlines()
        self.assertEqual([line.split()[1] for line in calls], ["T-100", "T-101", "T-105", "T-107", "T-108", "T-109", "T-110", "T-111"])

    def test_hidden_idempotent_and_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            (root / "scripts").mkdir(parents=True)
            (root / "api_state").mkdir()
            shutil.copy2(app / "scripts" / "apply_task.py", root / "scripts" / "apply_task.py")
            hidden = [
                {"id": "H-1", "title": "security low", "severity": "low", "type": "bug", "product_area": "docs", "priority": "P3", "owner": "support", "labels": ["security"]},
                {"id": "H-2", "title": "already done", "severity": "medium", "type": "bug", "product_area": "platform", "priority": "P2", "owner": "platform", "labels": ["triaged"]},
            ]
            (root / "api_state" / "tickets.json").write_text(json.dumps(hidden, indent=2))
            (root / "api_state" / "calls.log").write_text("")
            run(root)
            self.assert_reconciled(root, hidden)
            first_calls = (root / "api_state" / "calls.log").read_text()
            run(root)
            self.assertEqual((root / "api_state" / "calls.log").read_text(), "")
            self.assertIn("H-1", first_calls)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TicketBulkTriageTests)
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

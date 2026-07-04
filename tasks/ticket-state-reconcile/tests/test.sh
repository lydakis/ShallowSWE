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


def run_sync(root: Path, manifest: list[dict[str, object]], state: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]]]:
    manifest_path = root / "manifest.json"
    state_path = root / "state.json"
    output_path = root / "output.json"
    audit_path = root / "audit.jsonl"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    state_path.write_text(json.dumps(state, indent=2))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ticket_sync.cli",
            "--manifest",
            str(manifest_path),
            "--state",
            str(state_path),
            "--output-state",
            str(output_path),
            "--audit-log",
            str(audit_path),
        ],
        check=True,
    )
    audit_rows = [json.loads(line) for line in audit_path.read_text().splitlines()]
    return json.loads(output_path.read_text()), audit_rows


def by_id(state: dict[str, object]) -> dict[str, dict[str, object]]:
    return {ticket["id"]: ticket for ticket in state["tickets"]}


class HiddenTicketReconcileTests(unittest.TestCase):
    def test_reconcile_duplicates_transitions_retry_and_preserves_unmentioned(self) -> None:
        manifest = [
            {
                "external_key": " Billing.Retry ",
                "title": "Billing retry should stay open",
                "owner": "billing",
                "severity": "high",
                "desired_status": "open",
                "labels": ["billing", "retry"],
            },
            {
                "external_key": "ops.rotate-secret",
                "title": "Rotate stale ops secret",
                "owner": "ops",
                "severity": "medium",
                "desired_status": "closed",
                "labels": ["ops", "security"],
            },
            {
                "external_key": "support.new-sla",
                "title": "Add support SLA dashboard",
                "owner": "support",
                "severity": "medium",
                "desired_status": "open",
                "labels": ["support", "sla"],
            },
        ]
        state = {
            "tickets": [
                {
                    "id": "TKT-100",
                    "external_key": "billing.retry",
                    "title": "Old retry",
                    "owner": "billing",
                    "severity": "low",
                    "status": "closed",
                    "labels": ["billing"],
                    "archived": False,
                },
                {
                    "id": "TKT-101",
                    "external_key": "BILLING.RETRY",
                    "title": "Duplicate retry",
                    "owner": "billing",
                    "severity": "low",
                    "status": "open",
                    "labels": ["billing"],
                    "archived": False,
                },
                {
                    "id": "TKT-102",
                    "external_key": "billing.retry",
                    "title": "Archived retry",
                    "owner": "billing",
                    "severity": "low",
                    "status": "open",
                    "labels": ["old"],
                    "archived": True,
                },
                {
                    "id": "TKT-103",
                    "external_key": "ops.rotate-secret",
                    "title": "Rotate secret",
                    "owner": "ops",
                    "severity": "low",
                    "status": "open",
                    "labels": ["ops"],
                    "archived": False,
                },
                {
                    "id": "TKT-104",
                    "external_key": "platform.keep-open",
                    "title": "Keep platform ticket",
                    "owner": "platform",
                    "severity": "low",
                    "status": "open",
                    "labels": ["platform"],
                    "archived": False,
                },
            ],
            "transient_fail_once": ["update:billing.retry", "close:ops.rotate-secret"],
        }

        with tempfile.TemporaryDirectory() as tmp:
            output, audit = run_sync(Path(tmp), manifest, state)

        tickets = by_id(output)
        self.assertEqual(tickets["TKT-100"]["external_key"], " Billing.Retry ")
        self.assertEqual(tickets["TKT-100"]["title"], "Billing retry should stay open")
        self.assertEqual(tickets["TKT-100"]["severity"], "high")
        self.assertEqual(tickets["TKT-100"]["status"], "open")
        self.assertEqual(tickets["TKT-100"]["labels"], ["billing", "retry"])

        self.assertEqual(tickets["TKT-101"]["status"], "duplicate")
        self.assertEqual(tickets["TKT-101"]["duplicate_of"], "TKT-100")
        self.assertTrue(tickets["TKT-102"]["archived"])
        self.assertNotEqual(tickets["TKT-102"].get("duplicate_of"), "TKT-100")

        self.assertEqual(tickets["TKT-103"]["status"], "closed")
        self.assertEqual(tickets["TKT-103"]["severity"], "medium")
        self.assertEqual(tickets["TKT-104"]["status"], "open")

        self.assertEqual(tickets["TKT-105"]["external_key"], "support.new-sla")
        self.assertEqual(tickets["TKT-105"]["status"], "open")

        actions = [(row["action"], row["ticket_id"], row["external_key"]) for row in audit]
        self.assertIn(("dedupe", "TKT-101", " Billing.Retry "), actions)
        self.assertIn(("retry", "TKT-100", " Billing.Retry "), actions)
        self.assertIn(("reopen", "TKT-100", " Billing.Retry "), actions)
        self.assertIn(("retry", "TKT-103", "ops.rotate-secret"), actions)
        self.assertIn(("close", "TKT-103", "ops.rotate-secret"), actions)
        self.assertIn(("create", "TKT-105", "support.new-sla"), actions)

        for row in audit:
            self.assertEqual(set(row), {"action", "ticket_id", "external_key", "detail"})
        self.assertNotIn("delete", [entry["action"] for entry in output["call_log"]])

    def test_noop_when_state_already_matches(self) -> None:
        manifest = [
            {
                "external_key": "docs.ready",
                "title": "Docs are ready",
                "owner": "docs",
                "severity": "low",
                "desired_status": "open",
                "labels": ["docs"],
            }
        ]
        state = {
            "tickets": [
                {
                    "id": "TKT-200",
                    "external_key": "docs.ready",
                    "title": "Docs are ready",
                    "owner": "docs",
                    "severity": "low",
                    "status": "open",
                    "labels": ["docs"],
                    "archived": False,
                }
            ],
            "transient_fail_once": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            output, audit = run_sync(Path(tmp), manifest, state)

        self.assertEqual(output["tickets"][0]["id"], "TKT-200")
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["action"], "noop")
        self.assertEqual(audit[0]["ticket_id"], "TKT-200")
        self.assertEqual(audit[0]["external_key"], "docs.ready")
        self.assertIsInstance(audit[0]["detail"], str)
        self.assertTrue(audit[0]["detail"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenTicketReconcileTests)
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

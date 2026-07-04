from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


class BasicSyncTests(unittest.TestCase):
    def test_updates_existing_and_creates_missing_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = [
                {
                    "external_key": "billing.invoice-missing",
                    "title": "Invoice missing from export",
                    "owner": "billing",
                    "severity": "high",
                    "desired_status": "open",
                    "labels": ["billing", "export"],
                },
                {
                    "external_key": "support.new-sla",
                    "title": "Add support SLA dashboard",
                    "owner": "support",
                    "severity": "medium",
                    "desired_status": "open",
                    "labels": ["support"],
                },
            ]
            state = {
                "tickets": [
                    {
                        "id": "TKT-100",
                        "external_key": "billing.invoice-missing",
                        "title": "Old invoice title",
                        "owner": "billing",
                        "severity": "low",
                        "status": "open",
                        "labels": ["billing"],
                        "archived": False,
                    }
                ],
                "transient_fail_once": [],
            }
            manifest_path = root / "manifest.json"
            state_path = root / "state.json"
            output_path = root / "out.json"
            audit_path = root / "audit.jsonl"
            manifest_path.write_text(json.dumps(manifest))
            state_path.write_text(json.dumps(state))

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

            output = json.loads(output_path.read_text())
            tickets = {ticket["external_key"]: ticket for ticket in output["tickets"]}
            audit_text = audit_path.read_text()

        self.assertEqual(tickets["billing.invoice-missing"]["severity"], "high")
        self.assertEqual(tickets["support.new-sla"]["id"], "TKT-101")
        self.assertTrue(audit_text.strip())


if __name__ == "__main__":
    unittest.main()

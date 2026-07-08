from __future__ import annotations

from pathlib import Path
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest


APP_DIR = Path(os.environ.get("APP_DIR", "/app"))


def run_cli(state: Path, output: Path, audit: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "incident_comms.cli",
            "--timeline",
            str(APP_DIR / "fixtures" / "timeline.json"),
            "--state",
            str(state),
            "--output-state",
            str(output),
            "--audit-log",
            str(audit),
        ],
        check=True,
    )


def read_jsonl(path: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


class VisibleIncidentCommsTests(unittest.TestCase):
    def test_cli_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            output = tmp / "state.json"
            audit = tmp / "audit.jsonl"

            run_cli(APP_DIR / "fixtures" / "state.json", output, audit)

            self.assertTrue(output.exists())
            self.assertTrue(audit.exists())

    def test_replay_with_cleared_call_log_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            first_output = tmp / "state1.json"
            first_audit = tmp / "audit1.jsonl"
            replay_input = tmp / "replay-input.json"
            replay_output = tmp / "state2.json"
            replay_audit = tmp / "audit2.jsonl"

            run_cli(APP_DIR / "fixtures" / "state.json", first_output, first_audit)

            first_state = json.loads(first_output.read_text())
            first_rows = read_jsonl(first_audit)
            first_actions = [row["action"] for row in first_rows]
            call_actions = [row["action"] for row in first_state["call_log"]]
            self.assertIn("component_status", first_actions)
            self.assertIn("post_update", first_actions)
            self.assertIn("resolve_stale", first_actions)
            self.assertIn("enqueue_notification", first_actions)
            self.assertIn("update_incident", call_actions)
            self.assertNotIn("update_incident", first_actions)

            replay_state = copy.deepcopy(first_state)
            replay_state["call_log"] = []
            replay_input.write_text(json.dumps(replay_state, indent=2) + "\n")

            run_cli(replay_input, replay_output, replay_audit)

            replayed = json.loads(replay_output.read_text())
            self.assertEqual(replayed["components"], replay_state["components"])
            self.assertEqual(replayed["incidents"], replay_state["incidents"])
            self.assertEqual(replayed["notification_queue"], replay_state["notification_queue"])
            self.assertEqual(replayed["next_incident_number"], replay_state["next_incident_number"])
            self.assertEqual(replayed["call_log"], [])
            self.assertEqual(
                read_jsonl(replay_audit),
                [{"action": "noop", "target": "timeline", "detail": "already reconciled"}],
            )


if __name__ == "__main__":
    unittest.main()

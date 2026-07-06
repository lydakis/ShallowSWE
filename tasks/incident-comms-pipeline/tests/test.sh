#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json
import subprocess
import sys
import tempfile
import unittest


SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}
COMPONENT_SEVERITY = {
    "operational": "low",
    "degraded": "medium",
    "partial_outage": "high",
    "major_outage": "critical",
}


def run_pipeline(
    root: Path,
    timeline: dict[str, object],
    state: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    timeline_path = root / "timeline.json"
    state_path = root / "state.json"
    output_path = root / "output.json"
    audit_path = root / "audit.jsonl"
    timeline_path.write_text(json.dumps(timeline, indent=2))
    state_path.write_text(json.dumps(state, indent=2))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "incident_comms.cli",
            "--timeline",
            str(timeline_path),
            "--state",
            str(state_path),
            "--output-state",
            str(output_path),
            "--audit-log",
            str(audit_path),
        ],
        check=True,
    )
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()]
    return json.loads(output_path.read_text()), audit


def fixture_timeline() -> dict[str, object]:
    return json.loads(Path("/app/fixtures/timeline.json").read_text())


def fixture_state() -> dict[str, object]:
    return json.loads(Path("/app/fixtures/state.json").read_text())


def hidden_timeline() -> dict[str, object]:
    return {
        "events": [
            {
                "sequence": 30,
                "at": "2026-07-06T10:15:00Z",
                "type": "incident_update",
                "incident_key": "payments-timeouts",
                "status": "identified",
                "severity": "high",
                "components": ["payments", "api"],
                "update_key": "pay-002",
                "message": "Timeouts traced to the payment processor.",
            },
            {
                "sequence": 10,
                "at": "2026-07-06T10:00:00Z",
                "type": "component_status",
                "component": "payments",
                "component_status": "major_outage",
            },
            {
                "sequence": 20,
                "at": "2026-07-06T10:05:00Z",
                "type": "incident_opened",
                "incident_key": "payments-timeouts",
                "title": "Payment timeouts",
                "status": "investigating",
                "severity": "high",
                "components": ["payments"],
                "update_key": "pay-001",
                "message": "We are investigating elevated payment timeouts.",
            },
            {
                "sequence": 40,
                "at": "2026-07-06T10:15:00Z",
                "type": "incident_update",
                "incident_key": "payments-timeouts",
                "status": "identified",
                "severity": "high",
                "components": ["payments", "api"],
                "update_key": "pay-002",
                "message": "Duplicate timeline event should not repost.",
            },
            {
                "sequence": 50,
                "at": "2026-07-06T11:00:00Z",
                "type": "component_status",
                "component": "api",
                "component_status": "degraded",
            },
            {
                "sequence": 55,
                "at": "2026-07-06T11:10:00Z",
                "type": "component_status",
                "component": "email",
                "component_status": "degraded",
            },
            {
                "sequence": 60,
                "at": "2026-07-06T11:30:00Z",
                "type": "incident_resolved",
                "incident_key": "payments-timeouts",
                "status": "resolved",
                "severity": "medium",
                "components": ["payments", "api"],
                "update_key": "pay-003",
                "message": "Payment processing has recovered.",
            },
        ],
        "stale_incident_keys": ["email-delay", "already-resolved"],
        "stale_resolution_at": "2026-07-06T12:00:00Z",
    }


def hidden_state() -> dict[str, object]:
    return {
        "components": {"payments": "operational", "api": "operational", "email": "degraded"},
        "subscribers": {
            "api-oncall": {"components": ["api"], "minimum_severity": "medium"},
            "email-team": {"components": ["email"], "minimum_severity": "medium"},
            "payments-team": {"components": ["payments"], "minimum_severity": "low"},
            "platform-execs": {"components": ["*"], "minimum_severity": "critical"},
        },
        "notification_queue": [
            {
                "notification_key": "incident:pay-001:payments-team",
                "subscriber_id": "payments-team",
                "kind": "incident_update",
                "target": "INC-050",
                "at": "2026-07-06T10:05:00Z",
                "severity": "high",
                "message": "We are investigating elevated payment timeouts.",
            }
        ],
        "incidents": [
            {
                "id": "INC-050",
                "incident_key": "payments-timeouts",
                "title": "Payment timeouts",
                "status": "monitoring",
                "components": ["payments"],
                "updates": [
                    {
                        "update_key": "pay-001",
                        "at": "2026-07-06T10:05:00Z",
                        "status": "investigating",
                        "message": "We are investigating elevated payment timeouts.",
                    }
                ],
            },
            {
                "id": "INC-051",
                "incident_key": "email-delay",
                "title": "Email delivery delay",
                "status": "identified",
                "components": ["email"],
                "updates": [],
            },
            {
                "id": "INC-052",
                "incident_key": "already-resolved",
                "title": "Resolved auth issue",
                "status": "resolved",
                "components": ["api"],
                "updates": [
                    {
                        "update_key": "auth-001",
                        "at": "2026-07-06T08:00:00Z",
                        "status": "resolved",
                        "message": "Auth recovered.",
                    }
                ],
            },
        ],
        "next_incident_number": 53,
        "call_log": [],
    }


def audit(action: str, target: str, detail: str) -> dict[str, str]:
    return {"action": action, "target": target, "detail": detail}


def find_by_key(state: dict[str, Any], incident_key: str) -> dict[str, Any] | None:
    for incident in state["incidents"]:
        if incident["incident_key"] == incident_key:
            return incident
    return None


def update_keys(incident: dict[str, Any]) -> set[str]:
    return {update["update_key"] for update in incident.get("updates", [])}


def notification_keys(state: dict[str, Any]) -> set[str]:
    return {row["notification_key"] for row in state.get("notification_queue", [])}


def component_match(subscribed: list[str], affected: list[str]) -> bool:
    return "*" in subscribed or bool(set(subscribed).intersection(affected))


def severity_allows(minimum: str, severity: str) -> bool:
    return SEVERITY[severity] >= SEVERITY[minimum]


def call(state: dict[str, Any], action: str, target: str, detail: dict[str, object]) -> None:
    state["call_log"].append({"action": action, "target": target, "detail": detail})


def enqueue(
    state: dict[str, Any],
    rows: list[dict[str, str]],
    notification: dict[str, str],
) -> None:
    if notification["notification_key"] in notification_keys(state):
        return
    state["notification_queue"].append(notification)
    call(
        state,
        "enqueue_notification",
        notification["notification_key"],
        {"subscriber_id": notification["subscriber_id"], "kind": notification["kind"]},
    )
    rows.append(audit("enqueue_notification", notification["notification_key"], notification["subscriber_id"]))


def notify_component(
    state: dict[str, Any],
    rows: list[dict[str, str]],
    event: dict[str, Any],
    severity: str,
) -> None:
    component = event["component"]
    for subscriber_id, subscriber in sorted(state["subscribers"].items()):
        if not component_match(list(subscriber["components"]), [component]):
            continue
        if not severity_allows(str(subscriber["minimum_severity"]), severity):
            continue
        enqueue(
            state,
            rows,
            {
                "notification_key": (
                    f"component:{component}:{event['at']}:{event['sequence']}:{subscriber_id}"
                ),
                "subscriber_id": subscriber_id,
                "kind": "component_status",
                "target": component,
                "at": event["at"],
                "severity": severity,
                "message": f"{component} is {event['component_status']}",
            },
        )


def notify_incident(
    state: dict[str, Any],
    rows: list[dict[str, str]],
    incident: dict[str, Any],
    update: dict[str, str],
    severity: str,
) -> None:
    components = list(incident["components"])
    for subscriber_id, subscriber in sorted(state["subscribers"].items()):
        if not component_match(list(subscriber["components"]), components):
            continue
        if not severity_allows(str(subscriber["minimum_severity"]), severity):
            continue
        enqueue(
            state,
            rows,
            {
                "notification_key": f"incident:{update['update_key']}:{subscriber_id}",
                "subscriber_id": subscriber_id,
                "kind": "incident_update",
                "target": incident["id"],
                "at": update["at"],
                "severity": severity,
                "message": update["message"],
            },
        )


def expected(
    timeline: dict[str, object],
    original_state: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    state: dict[str, Any] = copy.deepcopy(original_state)
    state.setdefault("subscribers", {})
    state.setdefault("notification_queue", [])
    state.setdefault("call_log", [])
    rows: list[dict[str, str]] = []

    for event in sorted(timeline["events"], key=lambda item: (item["at"], int(item["sequence"]))):
        if event["type"] == "component_status":
            current = state["components"].get(event["component"])
            if current != event["component_status"]:
                state["components"][event["component"]] = event["component_status"]
                call(state, "component_status", event["component"], {"status": event["component_status"]})
                rows.append(audit("component_status", event["component"], event["component_status"]))
                notify_component(state, rows, event, COMPONENT_SEVERITY[event["component_status"]])
            continue

        incident = find_by_key(state, event["incident_key"])
        if incident is None:
            incident = {
                "id": f"INC-{int(state['next_incident_number'])}",
                "incident_key": event["incident_key"],
                "title": event.get("title") or event["incident_key"],
                "status": "investigating",
                "components": sorted(set(event.get("components") or [])),
                "updates": [],
            }
            state["next_incident_number"] = int(state["next_incident_number"]) + 1
            state["incidents"].append(incident)
            call(state, "create_incident", incident["id"], {"incident_key": event["incident_key"]})
            rows.append(audit("create_incident", incident["id"], f"created {event['incident_key']}"))

        status = "resolved" if event["type"] == "incident_resolved" else event.get("status", incident["status"])
        if event["type"] == "incident_opened" and incident["status"] == "resolved":
            status = "investigating"
        components = sorted(set(incident["components"]).union(event.get("components") or []))
        if incident["status"] != status or incident["components"] != components:
            incident["status"] = status
            incident["components"] = components
            call(state, "update_incident", incident["id"], {"fields": ["components", "status"]})

        if event["update_key"] not in update_keys(incident):
            update = {
                "update_key": event["update_key"],
                "at": event["at"],
                "status": status,
                "message": event["message"],
            }
            incident["updates"].append(update)
            call(state, "post_update", incident["id"], {"update_key": event["update_key"]})
            rows.append(audit("post_update", incident["id"], event["update_key"]))
            notify_incident(state, rows, incident, update, event["severity"])

    for incident_key in timeline.get("stale_incident_keys", []):
        incident = find_by_key(state, incident_key)
        if incident is None or incident["status"] == "resolved":
            continue
        update_key = f"stale-resolve:{incident_key}"
        incident["status"] = "resolved"
        call(state, "update_incident", incident["id"], {"fields": ["status"]})
        if update_key not in update_keys(incident):
            update = {
                "update_key": update_key,
                "at": timeline["stale_resolution_at"],
                "status": "resolved",
                "message": "Resolved as stale after reconciliation",
            }
            incident["updates"].append(update)
            call(state, "post_update", incident["id"], {"update_key": update_key})
            posted_update = True
        else:
            update = next(item for item in incident["updates"] if item["update_key"] == update_key)
            posted_update = False
        rows.append(audit("resolve_stale", incident["id"], incident_key))
        if posted_update:
            notify_incident(state, rows, incident, update, "low")

    state["incidents"] = sorted(state["incidents"], key=lambda incident: incident["id"])
    return state, rows or [audit("noop", "timeline", "already reconciled")]


def assert_audit_schema(test: unittest.TestCase, audit_rows: list[dict[str, str]]) -> None:
    allowed = {
        "component_status",
        "create_incident",
        "post_update",
        "resolve_stale",
        "enqueue_notification",
        "noop",
    }
    for row in audit_rows:
        test.assertEqual(set(row), {"action", "target", "detail"})
        test.assertIn(row["action"], allowed)
        test.assertIsInstance(row["detail"], str)
        test.assertTrue(row["detail"])


def assert_audit_actions(
    test: unittest.TestCase,
    audit_rows: list[dict[str, str]],
    expected_audit: list[dict[str, str]],
) -> None:
    test.assertEqual(
        [row["action"] for row in audit_rows],
        [row["action"] for row in expected_audit],
    )
    assert_audit_schema(test, audit_rows)


def assert_state_and_audit(
    test: unittest.TestCase,
    timeline: dict[str, object],
    start_state: dict[str, object],
    output: dict[str, object],
    audit_rows: list[dict[str, str]],
) -> None:
    expected_state, expected_audit = expected(timeline, start_state)
    test.maxDiff = None
    output_without_log = copy.deepcopy(output)
    expected_without_log = copy.deepcopy(expected_state)
    output_call_log = output_without_log.pop("call_log")
    expected_call_log = expected_without_log.pop("call_log")
    test.assertEqual(output_without_log, expected_without_log)
    test.assertEqual(
        [(row["action"], row["target"]) for row in output_call_log],
        [(row["action"], row["target"]) for row in expected_call_log],
    )
    assert_audit_actions(test, audit_rows, expected_audit)
    destructive = {"delete_incident", "delete_update", "delete_component", "delete_notification"}
    test.assertFalse({row["action"] for row in output_call_log}.intersection(destructive))
    test.assertEqual(
        len(output["notification_queue"]),
        len({row["notification_key"] for row in output["notification_queue"]}),
    )


class IncidentCommsPipelineTests(unittest.TestCase):
    def test_visible_reconciles_state_notifications_and_replay(self) -> None:
        timeline = fixture_timeline()
        start = fixture_state()
        with tempfile.TemporaryDirectory() as tmp:
            output, audit_rows = run_pipeline(Path(tmp), timeline, start)
        assert_state_and_audit(self, timeline, start, output, audit_rows)
        self.assertIn(
            "incident:stale-resolve:old-cache:cache-team",
            {row["notification_key"] for row in output["notification_queue"]},
        )

        replay_state = copy.deepcopy(output)
        replay_state["call_log"] = []
        with tempfile.TemporaryDirectory() as tmp:
            replay, replay_audit = run_pipeline(Path(tmp), timeline, replay_state)
        self.assertEqual(replay["components"], replay_state["components"])
        self.assertEqual(replay["incidents"], replay_state["incidents"])
        self.assertEqual(replay["notification_queue"], replay_state["notification_queue"])
        self.assertEqual(replay["next_incident_number"], replay_state["next_incident_number"])
        self.assertEqual(replay["call_log"], [])
        self.assertEqual(len(replay_audit), 1)
        self.assertEqual(replay_audit[0]["action"], "noop")
        assert_audit_schema(self, replay_audit)

    def test_hidden_exercises_dedupe_severity_filtering_and_stale_resolution(self) -> None:
        timeline = hidden_timeline()
        start = hidden_state()
        with tempfile.TemporaryDirectory() as tmp:
            output, audit_rows = run_pipeline(Path(tmp), timeline, start)
        assert_state_and_audit(self, timeline, start, output, audit_rows)
        keys = {row["notification_key"] for row in output["notification_queue"]}
        self.assertIn("component:payments:2026-07-06T10:00:00Z:10:platform-execs", keys)
        self.assertIn("incident:pay-002:api-oncall", keys)
        self.assertNotIn("incident:pay-003:platform-execs", keys)
        self.assertNotIn("incident:stale-resolve:email-delay:email-team", keys)

    def test_audit_and_call_log_do_not_hide_extra_mutations(self) -> None:
        timeline = hidden_timeline()
        start = hidden_state()
        with tempfile.TemporaryDirectory() as tmp:
            output, audit_rows = run_pipeline(Path(tmp), timeline, start)
        mutating_audit = [row for row in audit_rows if row["action"] != "noop"]
        self.assertGreater(len(mutating_audit), 8)
        self.assertEqual(
            [row["action"] for row in output["call_log"] if row["action"] == "enqueue_notification"],
            ["enqueue_notification"]
            * len([row for row in audit_rows if row["action"] == "enqueue_notification"]),
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IncidentCommsPipelineTests)
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

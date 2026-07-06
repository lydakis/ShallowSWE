#!/usr/bin/env bash
set -euo pipefail

cat > incident_comms/pipeline.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json

from .api import LocalStatuspageApi


RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
STATUS_RANK = {
    "operational": "low",
    "degraded": "medium",
    "partial_outage": "high",
    "major_outage": "critical",
}


@dataclass
class Reconciler:
    api: LocalStatuspageApi
    timeline: dict[str, Any]
    audit_rows: list[dict[str, str]]

    def emit(self, action: str, target: str, detail: str) -> None:
        self.audit_rows.append({"action": action, "target": target, "detail": detail})

    def existing_notifications(self) -> set[str]:
        return {item["notification_key"] for item in self.api.state.get("notification_queue", [])}

    def existing_updates(self, incident: dict[str, Any]) -> set[str]:
        return {item["update_key"] for item in incident.get("updates", [])}

    def subscriber_ids(self, components: Iterable[str], severity: str) -> list[str]:
        affected = set(components)
        ids: list[str] = []
        for subscriber_id, subscriber in sorted(self.api.state.get("subscribers", {}).items()):
            wanted = set(subscriber.get("components", []))
            if "*" not in wanted and not wanted.intersection(affected):
                continue
            if RANK[severity] < RANK[str(subscriber["minimum_severity"])]:
                continue
            ids.append(subscriber_id)
        return ids

    def enqueue(self, notification: dict[str, str]) -> None:
        if notification["notification_key"] in self.existing_notifications():
            return
        self.api.enqueue_notification(notification)
        self.emit("enqueue_notification", notification["notification_key"], notification["subscriber_id"])

    def component_changed(self, event: dict[str, Any]) -> None:
        component = event["component"]
        status = event["component_status"]
        if self.api.state["components"].get(component) == status:
            return
        self.api.set_component_status(component, status)
        self.emit("component_status", component, status)
        severity = STATUS_RANK[status]
        for subscriber_id in self.subscriber_ids([component], severity):
            self.enqueue(
                {
                    "notification_key": (
                        f"component:{component}:{event['at']}:{event['sequence']}:{subscriber_id}"
                    ),
                    "subscriber_id": subscriber_id,
                    "kind": "component_status",
                    "target": component,
                    "at": event["at"],
                    "severity": severity,
                    "message": f"{component} is {status}",
                }
            )

    def incident_for(self, event: dict[str, Any]) -> dict[str, Any]:
        incident = self.api.find_by_key(event["incident_key"])
        if incident is not None:
            return incident
        incident = self.api.create_incident(
            event["incident_key"],
            event.get("title") or event["incident_key"],
            "investigating",
            list(event.get("components") or []),
        )
        self.emit("create_incident", incident["id"], f"created {event['incident_key']}")
        return incident

    def reconcile_incident_event(self, event: dict[str, Any]) -> None:
        incident = self.incident_for(event)
        status = "resolved" if event["type"] == "incident_resolved" else event.get("status", incident["status"])
        if event["type"] == "incident_opened" and incident["status"] == "resolved":
            status = "investigating"
        components = sorted(set(incident["components"]) | set(event.get("components") or []))
        if status != incident["status"] or components != incident["components"]:
            self.api.update_incident(incident["id"], {"status": status, "components": components})
            incident = self.api.find_by_id(incident["id"])
        if event["update_key"] in self.existing_updates(incident):
            return
        update = {
            "update_key": event["update_key"],
            "at": event["at"],
            "status": status,
            "message": event["message"],
        }
        self.api.post_update(incident["id"], update)
        self.emit("post_update", incident["id"], event["update_key"])
        incident = self.api.find_by_id(incident["id"])
        for subscriber_id in self.subscriber_ids(incident["components"], event["severity"]):
            self.enqueue(
                {
                    "notification_key": f"incident:{update['update_key']}:{subscriber_id}",
                    "subscriber_id": subscriber_id,
                    "kind": "incident_update",
                    "target": incident["id"],
                    "at": update["at"],
                    "severity": event["severity"],
                    "message": update["message"],
                }
            )

    def resolve_stale(self) -> None:
        for incident_key in self.timeline.get("stale_incident_keys", []):
            incident = self.api.find_by_key(incident_key)
            if incident is None or incident["status"] == "resolved":
                continue
            self.api.update_incident(incident["id"], {"status": "resolved"})
            incident = self.api.find_by_id(incident["id"])
            update_key = f"stale-resolve:{incident_key}"
            posted = False
            if update_key not in self.existing_updates(incident):
                update = {
                    "update_key": update_key,
                    "at": self.timeline["stale_resolution_at"],
                    "status": "resolved",
                    "message": "Resolved as stale after reconciliation",
                }
                self.api.post_update(incident["id"], update)
                posted = True
            else:
                update = next(item for item in incident["updates"] if item["update_key"] == update_key)
            self.emit("resolve_stale", incident["id"], incident_key)
            if not posted:
                continue
            for subscriber_id in self.subscriber_ids(incident["components"], "low"):
                self.enqueue(
                    {
                        "notification_key": f"incident:{update_key}:{subscriber_id}",
                        "subscriber_id": subscriber_id,
                        "kind": "incident_update",
                        "target": incident["id"],
                        "at": update["at"],
                        "severity": "low",
                        "message": update["message"],
                    }
                )

    def run(self) -> None:
        for event in sorted(self.timeline.get("events", []), key=lambda item: (item["at"], int(item["sequence"]))):
            if event["type"] == "component_status":
                self.component_changed(event)
            else:
                self.reconcile_incident_event(event)
        self.resolve_stale()


def final_components(timeline: dict[str, Any]) -> dict[str, str]:
    wanted: dict[str, str] = {}
    for event in sorted(timeline.get("events", []), key=lambda item: (item["at"], int(item["sequence"]))):
        if event["type"] == "component_status":
            wanted[event["component"]] = event["component_status"]
    return wanted


def notification_keys(api: LocalStatuspageApi) -> set[str]:
    return {item["notification_key"] for item in api.state.get("notification_queue", [])}


def update_keys(incident: dict[str, Any]) -> set[str]:
    return {item["update_key"] for item in incident.get("updates", [])}


def subscriber_matches(subscriber: dict[str, Any], components: list[str], severity: str) -> bool:
    wanted = set(subscriber.get("components", []))
    return ("*" in wanted or bool(wanted.intersection(components))) and (
        RANK[severity] >= RANK[str(subscriber["minimum_severity"])]
    )


def required_notification_keys(
    api: LocalStatuspageApi,
    update_key: str,
    severity: str,
    components: list[str],
) -> set[str]:
    return {
        f"incident:{update_key}:{subscriber_id}"
        for subscriber_id, subscriber in api.state.get("subscribers", {}).items()
        if subscriber_matches(subscriber, components, severity)
    }


def already_reconciled(api: LocalStatuspageApi, timeline: dict[str, Any]) -> bool:
    for component, status in final_components(timeline).items():
        if api.state["components"].get(component) != status:
            return False

    existing_notifications = notification_keys(api)
    final_incident_status: dict[str, str] = {}
    for event in sorted(timeline.get("events", []), key=lambda item: (item["at"], int(item["sequence"]))):
        if event["type"] == "component_status":
            continue
        incident = api.find_by_key(event["incident_key"])
        if incident is None or event["update_key"] not in update_keys(incident):
            return False
        if not set(event.get("components") or []).issubset(set(incident.get("components", []))):
            return False
        final_incident_status[event["incident_key"]] = (
            "resolved" if event["type"] == "incident_resolved" else event.get("status", incident["status"])
        )
        components = list(event.get("components") or incident.get("components", []))
        required = required_notification_keys(api, event["update_key"], event["severity"], components)
        if not required.issubset(existing_notifications):
            return False

    for incident_key, status in final_incident_status.items():
        incident = api.find_by_key(incident_key)
        if incident is None or incident["status"] != status:
            return False

    for incident_key in timeline.get("stale_incident_keys", []):
        incident = api.find_by_key(incident_key)
        if incident is None:
            continue
        update_key = f"stale-resolve:{incident_key}"
        if incident["status"] != "resolved" or update_key not in update_keys(incident):
            return False
        required = required_notification_keys(api, update_key, "low", list(incident.get("components", [])))
        if not required.issubset(existing_notifications):
            return False
    return True


def write_jsonl(path: str | Path, rows: list[dict[str, str]]) -> None:
    Path(path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def reconcile(api: LocalStatuspageApi, timeline: dict[str, Any], audit_path: str | Path) -> None:
    if already_reconciled(api, timeline):
        write_jsonl(audit_path, [{"action": "noop", "target": "timeline", "detail": "already reconciled"}])
        return
    rows: list[dict[str, str]] = []
    Reconciler(api=api, timeline=timeline, audit_rows=rows).run()
    if not rows:
        rows = [{"action": "noop", "target": "timeline", "detail": "already reconciled"}]
    write_jsonl(audit_path, rows)
PY

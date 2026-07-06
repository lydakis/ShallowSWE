#!/usr/bin/env bash
set -euo pipefail

cat > incident_comms/pipeline.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalStatuspageApi


SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}
COMPONENT_SEVERITY = {
    "operational": "low",
    "degraded": "medium",
    "partial_outage": "high",
    "major_outage": "critical",
}


def audit(action: str, target: str, detail: str) -> dict[str, str]:
    return {"action": action, "target": target, "detail": detail}


def update_keys(incident: dict[str, Any]) -> set[str]:
    return {update["update_key"] for update in incident.get("updates", [])}


def notification_keys(api: LocalStatuspageApi) -> set[str]:
    return {row["notification_key"] for row in api.state.get("notification_queue", [])}


def matches(subscriber: dict[str, Any], components: list[str], severity: str) -> bool:
    subscribed = list(subscriber.get("components", []))
    component_ok = "*" in subscribed or bool(set(subscribed).intersection(components))
    severity_ok = SEVERITY[severity] >= SEVERITY[str(subscriber["minimum_severity"])]
    return component_ok and severity_ok


def enqueue(api: LocalStatuspageApi, rows: list[dict[str, str]], notification: dict[str, str]) -> None:
    if notification["notification_key"] in notification_keys(api):
        return
    api.enqueue_notification(notification)
    rows.append(audit("enqueue_notification", notification["notification_key"], notification["subscriber_id"]))


def notify_component(
    api: LocalStatuspageApi,
    rows: list[dict[str, str]],
    event: dict[str, Any],
    severity: str,
) -> None:
    component = event["component"]
    for subscriber_id, subscriber in sorted(api.state.get("subscribers", {}).items()):
        if not matches(subscriber, [component], severity):
            continue
        enqueue(
            api,
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
    api: LocalStatuspageApi,
    rows: list[dict[str, str]],
    incident: dict[str, Any],
    update: dict[str, str],
    severity: str,
) -> None:
    components = list(incident.get("components", []))
    for subscriber_id, subscriber in sorted(api.state.get("subscribers", {}).items()):
        if not matches(subscriber, components, severity):
            continue
        enqueue(
            api,
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


def ensure_incident(api: LocalStatuspageApi, event: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    incident = api.find_by_key(event["incident_key"])
    if incident is not None:
        return incident
    incident = api.create_incident(
        event["incident_key"],
        event.get("title") or event["incident_key"],
        "investigating",
        list(event.get("components") or []),
    )
    rows.append(audit("create_incident", incident["id"], f"created {event['incident_key']}"))
    return incident


def reconcile_event(api: LocalStatuspageApi, event: dict[str, Any], rows: list[dict[str, str]]) -> None:
    if event["type"] == "component_status":
        current = api.state["components"].get(event["component"])
        if current == event["component_status"]:
            return
        api.set_component_status(event["component"], event["component_status"])
        rows.append(audit("component_status", event["component"], event["component_status"]))
        notify_component(api, rows, event, COMPONENT_SEVERITY[event["component_status"]])
        return

    incident = ensure_incident(api, event, rows)
    status = "resolved" if event["type"] == "incident_resolved" else event.get("status", incident["status"])
    if event["type"] == "incident_opened" and incident["status"] == "resolved":
        status = "investigating"
    components = sorted(set(incident["components"]).union(event.get("components") or []))
    if incident["status"] != status or incident["components"] != components:
        api.update_incident(incident["id"], {"status": status, "components": components})
        incident = api.find_by_id(incident["id"])

    if event["update_key"] in update_keys(incident):
        return
    update = {
        "update_key": event["update_key"],
        "at": event["at"],
        "status": status,
        "message": event["message"],
    }
    api.post_update(incident["id"], update)
    rows.append(audit("post_update", incident["id"], event["update_key"]))
    incident = api.find_by_id(incident["id"])
    notify_incident(api, rows, incident, update, event["severity"])


def resolve_stale(api: LocalStatuspageApi, timeline: dict[str, Any], rows: list[dict[str, str]]) -> None:
    for incident_key in timeline.get("stale_incident_keys", []):
        incident = api.find_by_key(incident_key)
        if incident is None or incident["status"] == "resolved":
            continue
        api.update_incident(incident["id"], {"status": "resolved"})
        incident = api.find_by_id(incident["id"])
        update_key = f"stale-resolve:{incident_key}"
        posted = False
        if update_key not in update_keys(incident):
            update = {
                "update_key": update_key,
                "at": timeline["stale_resolution_at"],
                "status": "resolved",
                "message": "Resolved as stale after reconciliation",
            }
            api.post_update(incident["id"], update)
            posted = True
        else:
            update = next(item for item in incident["updates"] if item["update_key"] == update_key)
        rows.append(audit("resolve_stale", incident["id"], incident_key))
        if posted:
            notify_incident(api, rows, incident, update, "low")


def final_component_statuses(timeline: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for event in sorted(timeline.get("events", []), key=lambda row: (row["at"], int(row["sequence"]))):
        if event["type"] == "component_status":
            statuses[event["component"]] = event["component_status"]
    return statuses


def required_incident_notification_keys(
    api: LocalStatuspageApi,
    update_key: str,
    severity: str,
    components: list[str],
) -> set[str]:
    keys: set[str] = set()
    for subscriber_id, subscriber in sorted(api.state.get("subscribers", {}).items()):
        if matches(subscriber, components, severity):
            keys.add(f"incident:{update_key}:{subscriber_id}")
    return keys


def already_reconciled(api: LocalStatuspageApi, timeline: dict[str, Any]) -> bool:
    existing_notifications = notification_keys(api)
    for component, status in final_component_statuses(timeline).items():
        if api.state["components"].get(component) != status:
            return False

    final_status_by_key: dict[str, str] = {}
    for event in sorted(timeline.get("events", []), key=lambda row: (row["at"], int(row["sequence"]))):
        if event["type"] == "component_status":
            continue
        incident = api.find_by_key(event["incident_key"])
        if incident is None or event["update_key"] not in update_keys(incident):
            return False
        if not set(event.get("components") or []).issubset(set(incident.get("components", []))):
            return False
        final_status_by_key[event["incident_key"]] = (
            "resolved" if event["type"] == "incident_resolved" else event.get("status", incident["status"])
        )
        components = list(event.get("components") or incident.get("components", []))
        required = required_incident_notification_keys(api, event["update_key"], event["severity"], components)
        if not required.issubset(existing_notifications):
            return False

    for incident_key, status in final_status_by_key.items():
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
        required = required_incident_notification_keys(api, update_key, "low", list(incident.get("components", [])))
        if not required.issubset(existing_notifications):
            return False
    return True


def write_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    Path(path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def reconcile(api: LocalStatuspageApi, timeline: dict[str, Any], audit_path: str | Path) -> None:
    if already_reconciled(api, timeline):
        write_rows(audit_path, [audit("noop", "timeline", "already reconciled")])
        return
    rows: list[dict[str, str]] = []
    for event in sorted(timeline.get("events", []), key=lambda row: (row["at"], int(row["sequence"]))):
        reconcile_event(api, event, rows)
    resolve_stale(api, timeline, rows)
    write_rows(audit_path, rows or [audit("noop", "timeline", "already reconciled")])
PY

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalStatuspageApi


def _audit(action: str, target: str, detail: str) -> dict[str, str]:
    return {"action": action, "target": target, "detail": detail}


def reconcile(api: LocalStatuspageApi, timeline: dict[str, Any], audit_path: str | Path) -> None:
    """Naive seed implementation that appends updates and misses stale resolution."""
    rows: list[dict[str, str]] = []
    for event in timeline.get("events", []):
        if event["type"] == "component_status":
            api.set_component_status(event["component"], event["component_status"])
            rows.append(_audit("component_status", event["component"], event["component_status"]))
            continue
        incident = api.find_by_key(event["incident_key"])
        if incident is None:
            incident = api.create_incident(
                event["incident_key"],
                event.get("title") or event["incident_key"],
                event.get("status") or "investigating",
                list(event.get("components") or []),
            )
            rows.append(_audit("create_incident", incident["id"], event["incident_key"]))
        incident["status"] = event.get("status") or incident["status"]
        incident["components"] = list(event.get("components") or incident["components"])
        update = {
            "update_key": event["update_key"],
            "at": event["at"],
            "status": incident["status"],
            "message": event["message"],
        }
        api.post_update(incident["id"], update)
        rows.append(_audit("post_update", incident["id"], event["update_key"]))

    if not rows:
        rows.append(_audit("noop", "timeline", "no changes"))
    Path(audit_path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

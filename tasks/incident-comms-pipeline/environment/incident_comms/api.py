from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json


class LocalStatuspageApi:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = copy.deepcopy(state)
        self.state.setdefault("components", {})
        self.state.setdefault("incidents", [])
        self.state.setdefault("subscribers", {})
        self.state.setdefault("notification_queue", [])
        self.state.setdefault("next_incident_number", 1)
        self.state.setdefault("call_log", [])

    @classmethod
    def load(cls, path: str | Path) -> "LocalStatuspageApi":
        return cls(json.loads(Path(path).read_text()))

    def dump(self, path: str | Path) -> None:
        output = copy.deepcopy(self.state)
        output["incidents"] = sorted(output["incidents"], key=lambda incident: incident["id"])
        Path(path).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")

    def set_component_status(self, component: str, status: str) -> None:
        self.state["components"][component] = status
        self._log("component_status", component, {"status": status})

    def create_incident(self, incident_key: str, title: str, status: str, components: list[str]) -> dict[str, Any]:
        incident = {
            "id": f"INC-{int(self.state['next_incident_number'])}",
            "incident_key": incident_key,
            "title": title,
            "status": status,
            "components": sorted(set(components)),
            "updates": [],
        }
        self.state["next_incident_number"] = int(self.state["next_incident_number"]) + 1
        self.state["incidents"].append(incident)
        self._log("create_incident", incident["id"], {"incident_key": incident_key})
        return incident

    def update_incident(self, incident_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        incident = self.find_by_id(incident_id)
        incident.update(copy.deepcopy(fields))
        self._log("update_incident", incident_id, {"fields": sorted(fields)})
        return incident

    def post_update(self, incident_id: str, update: dict[str, str]) -> None:
        incident = self.find_by_id(incident_id)
        incident["updates"].append(copy.deepcopy(update))
        self._log("post_update", incident_id, {"update_key": update["update_key"]})

    def enqueue_notification(self, notification: dict[str, str]) -> None:
        self.state["notification_queue"].append(copy.deepcopy(notification))
        self._log(
            "enqueue_notification",
            notification["notification_key"],
            {
                "subscriber_id": notification["subscriber_id"],
                "kind": notification["kind"],
            },
        )

    def find_by_key(self, incident_key: str) -> dict[str, Any] | None:
        for incident in self.state["incidents"]:
            if incident["incident_key"] == incident_key:
                return incident
        return None

    def find_by_id(self, incident_id: str) -> dict[str, Any]:
        for incident in self.state["incidents"]:
            if incident["id"] == incident_id:
                return incident
        raise KeyError(incident_id)

    def _log(self, action: str, target: str, detail: dict[str, Any]) -> None:
        self.state["call_log"].append({"action": action, "target": target, "detail": detail})

from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json


class LocalDeployApi:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = copy.deepcopy(state)
        self.state.setdefault("services", {})
        self.state.setdefault("call_log", [])

    @classmethod
    def load(cls, path: str | Path) -> "LocalDeployApi":
        return cls(json.loads(Path(path).read_text()))

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n")

    def ring_version(self, service: str, ring: str) -> str | None:
        return self.state["services"].get(service, {}).get("rings", {}).get(ring)

    def deploy_ring(self, service: str, ring: str, version: str) -> None:
        service_state = self.state["services"].setdefault(service, {"rings": {}, "history": []})
        service_state.setdefault("rings", {})[ring] = version
        record = {"action": "deploy", "service": service, "ring": ring, "version": version}
        if record not in service_state.setdefault("history", []):
            service_state["history"].append(record)
            self._log("deploy", service, ring, {"version": version})

    def record_block(self, service: str, ring: str, reason: str) -> None:
        service_state = self.state["services"].setdefault(service, {"rings": {}, "history": []})
        record = {"action": "blocked", "service": service, "ring": ring, "reason": reason}
        if record not in service_state.setdefault("history", []):
            service_state["history"].append(record)
            self._log("blocked", service, ring, {"reason": reason})

    def _log(self, action: str, service: str, ring: str, detail: dict[str, Any]) -> None:
        self.state["call_log"].append(
            {"action": action, "service": service, "ring": ring, "detail": detail}
        )

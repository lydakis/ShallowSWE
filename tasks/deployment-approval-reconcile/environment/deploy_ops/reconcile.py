from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalDeployApi


def audit(action: str, service: str, ring: str, detail: str) -> dict[str, str]:
    return {"action": action, "service": service, "ring": ring, "detail": detail}


def reconcile(api: LocalDeployApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    """Seed implementation: deploys every listed ring and ignores gates."""
    rows: list[dict[str, str]] = []
    ring_order = plan.get("ring_order", [])
    for deployment in plan.get("deployments", []):
        service = deployment["service"]
        target = deployment["target_version"]
        for ring in ring_order:
            if ring not in deployment.get("rings", []):
                continue
            if api.ring_version(service, ring) == target:
                rows.append(audit("already_current", service, ring, target))
                continue
            api.deploy_ring(service, ring, target)
            rows.append(audit("deploy", service, ring, target))
    Path(audit_path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

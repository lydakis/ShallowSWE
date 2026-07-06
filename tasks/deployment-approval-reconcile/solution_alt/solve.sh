#!/usr/bin/env bash
set -euo pipefail

cat > deploy_ops/reconcile.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalDeployApi


def row(action: str, service: str, ring: str, detail: str) -> dict[str, str]:
    return {"action": action, "service": service, "ring": ring, "detail": detail}


def reconcile(api: LocalDeployApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    checks = {
        (item["service"], item["target_version"], item["ring"], item["check"]): item["result"]
        for item in plan.get("checks", [])
    }
    approvals = {
        (item["service"], item["target_version"], item["ring"])
        for item in plan.get("approvals", [])
        if item.get("approved") is True
    }

    def freeze_blocks(service: str, ring: str) -> bool:
        return any(
            window["service"] == service
            and window["ring"] == ring
            and window["start"] <= plan["now"] < window["end"]
            for window in plan.get("freeze_windows", [])
        )

    audit_rows: list[dict[str, str]] = []
    for dep in plan.get("deployments", []):
        service = dep["service"]
        target = dep["target_version"]
        rings = [ring for ring in plan.get("ring_order", []) if ring in dep.get("rings", [])]
        emitted = False
        for position, ring in enumerate(rings):
            current = api.ring_version(service, ring)
            if current == target:
                audit_rows.append(row("already_current", service, ring, target))
                emitted = True
                continue
            missing_prior = None
            for prior in rings[:position]:
                if api.ring_version(service, prior) != target:
                    missing_prior = prior
                    break
            if missing_prior is not None:
                reason = f"prior_ring_not_deployed:{missing_prior}"
            elif freeze_blocks(service, ring):
                reason = "freeze_window"
            elif ring in dep.get("approval_required_for", []) and (service, target, ring) not in approvals:
                reason = "missing_approval"
            else:
                reason = None
                for check in dep.get("required_checks", {}).get(ring, []):
                    result = checks.get((service, target, ring, check))
                    if result is None:
                        reason = f"missing_check:{check}"
                        break
                    if result != "pass":
                        reason = f"failed_check:{check}"
                        break
            if reason:
                api.record_block(service, ring, reason)
                audit_rows.append(row("blocked", service, ring, reason))
                emitted = True
                break
            api.deploy_ring(service, ring, target)
            audit_rows.append(row("deploy", service, ring, target))
            emitted = True
        if not emitted:
            audit_rows.append(row("noop", service, "*", "no changes"))
    Path(audit_path).write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in audit_rows))
PY

#!/usr/bin/env bash
set -euo pipefail

cat > deploy_ops/reconcile.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalDeployApi


def audit(action: str, service: str, ring: str, detail: str) -> dict[str, str]:
    return {"action": action, "service": service, "ring": ring, "detail": detail}


def _checks(plan: dict[str, Any]) -> dict[tuple[str, str, str, str], str]:
    return {
        (item["service"], item["target_version"], item["ring"], item["check"]): item["result"]
        for item in plan.get("checks", [])
    }


def _approvals(plan: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (item["service"], item["target_version"], item["ring"])
        for item in plan.get("approvals", [])
        if item.get("approved") is True
    }


def _frozen(plan: dict[str, Any], service: str, ring: str) -> bool:
    now = plan["now"]
    return any(
        item["service"] == service and item["ring"] == ring and item["start"] <= now < item["end"]
        for item in plan.get("freeze_windows", [])
    )


def reconcile(api: LocalDeployApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    rows: list[dict[str, str]] = []
    check_results = _checks(plan)
    approved = _approvals(plan)
    ring_order = plan.get("ring_order", [])

    for deployment in plan.get("deployments", []):
        service = deployment["service"]
        target = deployment["target_version"]
        listed = [ring for ring in ring_order if ring in deployment.get("rings", [])]
        wrote = False
        for index, ring in enumerate(listed):
            if api.ring_version(service, ring) == target:
                rows.append(audit("already_current", service, ring, target))
                wrote = True
                continue
            prior = next((item for item in listed[:index] if api.ring_version(service, item) != target), None)
            reason = None
            if prior is not None:
                reason = f"prior_ring_not_deployed:{prior}"
            elif _frozen(plan, service, ring):
                reason = "freeze_window"
            elif ring in deployment.get("approval_required_for", []) and (service, target, ring) not in approved:
                reason = "missing_approval"
            else:
                for check in deployment.get("required_checks", {}).get(ring, []):
                    result = check_results.get((service, target, ring, check))
                    if result is None:
                        reason = f"missing_check:{check}"
                        break
                    if result != "pass":
                        reason = f"failed_check:{check}"
                        break
            if reason is not None:
                api.record_block(service, ring, reason)
                rows.append(audit("blocked", service, ring, reason))
                wrote = True
                break
            api.deploy_ring(service, ring, target)
            rows.append(audit("deploy", service, ring, target))
            wrote = True
        if not wrote:
            rows.append(audit("noop", service, "*", "no changes"))

    Path(audit_path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
PY

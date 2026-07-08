#!/usr/bin/env bash
set -euo pipefail

cat > deploy_ops/reconcile.py <<'PY'
from __future__ import annotations

from collections import Counter
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


def _change_requests(plan: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (item["service"], item["target_version"], item["ring"]): item
        for item in plan.get("change_requests", [])
    }


def _frozen(plan: dict[str, Any], service: str, ring: str) -> bool:
    now = plan["now"]
    return any(
        item["service"] == service and item["ring"] == ring and item["start"] <= now < item["end"]
        for item in plan.get("freeze_windows", [])
    )


def _notify(state: dict[str, Any], plan: dict[str, Any], item: dict[str, str]) -> None:
    if item["action"] not in {"deploy", "blocked"}:
        return
    owner = plan.get("service_owners", {}).get(item["service"], "unassigned")
    key = f"{item['service']}:{item['ring']}:{item['action']}:{item['detail']}"
    notification = {
        "key": key,
        "service": item["service"],
        "ring": item["ring"],
        "owner": owner,
        "kind": item["action"],
        "detail": item["detail"],
    }
    notifications = state.setdefault("notifications", [])
    if not any(existing.get("key") == key for existing in notifications):
        notifications.append(notification)


def _summary(plan: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    counts = Counter(row["action"] for row in rows)
    blocked_services = sorted({row["service"] for row in rows if row["action"] == "blocked"})
    owners = plan.get("service_owners", {})
    return {
        "generated_at": plan["now"],
        "deployments_attempted": len(plan.get("deployments", [])),
        "deployed": counts["deploy"],
        "already_current": counts["already_current"],
        "blocked": counts["blocked"],
        "noop": counts["noop"],
        "changed_services": sorted({row["service"] for row in rows if row["action"] == "deploy"}),
        "blocked_services": blocked_services,
        "owners_to_page": sorted({owners.get(service, "unassigned") for service in blocked_services}),
    }


def reconcile(
    api: LocalDeployApi,
    plan: dict[str, Any],
    audit_path: str | Path,
    summary_path: str | Path,
) -> None:
    rows: list[dict[str, str]] = []
    check_results = _checks(plan)
    approved = _approvals(plan)
    requests = _change_requests(plan)
    ring_order = plan.get("ring_order", [])
    api.state.setdefault("notifications", [])

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
            elif ring in deployment.get("change_request_required_for", []):
                request = requests.get((service, target, ring))
                if request is None:
                    reason = "missing_change_request"
                elif request.get("status") != "approved":
                    reason = f"rejected_change_request:{request['request_id']}"

            if reason is None:
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
                item = audit("blocked", service, ring, reason)
                rows.append(item)
                _notify(api.state, plan, item)
                wrote = True
                break

            api.deploy_ring(service, ring, target)
            item = audit("deploy", service, ring, target)
            rows.append(item)
            _notify(api.state, plan, item)
            wrote = True

        if not wrote:
            rows.append(audit("noop", service, "*", "no changes"))

    Path(audit_path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    Path(summary_path).write_text(json.dumps(_summary(plan, rows), indent=2, sort_keys=True) + "\n")
PY

cat > deploy_ops/cli.py <<'PY'
from __future__ import annotations

import argparse
import json

from .api import LocalDeployApi
from .reconcile import reconcile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-state", required=True)
    parser.add_argument("--audit-log", required=True)
    parser.add_argument("--summary-report", required=True)
    args = parser.parse_args()

    api = LocalDeployApi.load(args.state)
    plan = json.loads(open(args.plan).read())
    reconcile(api, plan, args.audit_log, args.summary_report)
    api.dump(args.output_state)


if __name__ == "__main__":
    main()
PY

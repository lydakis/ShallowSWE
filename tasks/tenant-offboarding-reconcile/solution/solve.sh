#!/usr/bin/env bash
set -euo pipefail

mkdir -p scripts
cat > scripts/process_offboarding.py <<'PY'
from __future__ import annotations

from pathlib import Path
import argparse
import json


STATE_FILES = [
    "runbook.json",
    "tenants.json",
    "memberships.json",
    "sessions.json",
    "api_keys.json",
    "invites.json",
    "exports.json",
    "tickets.json",
    "integrations.json",
    "billing_accounts.json",
    "legal_holds.json",
    "call_log.json",
    "audit_log.json",
]


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_state(state_dir: Path) -> dict[str, object]:
    return {name: read_json(state_dir / name) for name in STATE_FILES}


def save_state(state_dir: Path, state: dict[str, object]) -> None:
    for name in STATE_FILES:
        write_json(state_dir / name, state[name])


def append_call(
    call_log: list[dict[str, object]],
    request_id: str,
    tenant_id: str,
    action: str,
    target_id: str,
) -> None:
    if any(
        row["request_id"] == request_id
        and row["tenant_id"] == tenant_id
        and row["action"] == action
        and row["target_id"] == target_id
        for row in call_log
    ):
        return
    max_sequence = max((int(row["sequence"]) for row in call_log), default=0)
    call_log.append(
        {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "action": action,
            "target_id": target_id,
            "sequence": max_sequence + 1,
        }
    )


def summary_from(state: dict[str, object]) -> dict[str, int]:
    run_date = state["runbook.json"]["run_date"]
    requests = state["runbook.json"]["requests"]
    tenants = state["tenants.json"]
    call_log = state["call_log.json"]
    counts: dict[str, int] = {}
    for row in call_log:
        counts[str(row["action"])] = counts.get(str(row["action"]), 0) + 1
    return {
        "processed_requests": sum(
            1
            for row in requests
            if row.get("status") == "completed" and row.get("completed_at") == run_date
        ),
        "closed_tenants": sum(1 for row in tenants if row["status"] == "closed"),
        "hold_review_tenants": sum(1 for row in tenants if row["status"] == "hold_review"),
        "revoked_sessions": counts.get("revoke_session", 0),
        "disabled_api_keys": counts.get("disable_api_key", 0),
        "canceled_invites": counts.get("cancel_invite", 0),
        "disabled_memberships": counts.get("disable_membership", 0),
        "disabled_integrations": counts.get("disable_integration", 0),
        "parked_domains": counts.get("park_domain", 0),
        "domain_reviews": counts.get("review_domain", 0),
        "closed_billing_accounts": counts.get("close_billing", 0),
        "held_billing_accounts": counts.get("hold_billing", 0),
        "collection_locks": counts.get("lock_collections", 0),
        "queued_tickets": counts.get("queue_ticket", 0),
        "retained_exports": counts.get("retain_export", 0),
        "canceled_exports": counts.get("cancel_export", 0),
        "expired_exports": counts.get("expire_export", 0),
        "call_log_entries": len(call_log),
    }


def process(state: dict[str, object]) -> dict[str, int]:
    runbook = state["runbook.json"]
    run_date = str(runbook["run_date"])
    call_log = state["call_log.json"]
    tenants = {str(row["tenant_id"]): row for row in state["tenants.json"]}
    active_holds_by_tenant: dict[str, list[dict[str, object]]] = {}
    for hold in state["legal_holds.json"]:
        if hold["status"] == "active":
            active_holds_by_tenant.setdefault(str(hold["tenant_id"]), []).append(hold)

    requests = sorted(
        [
            row
            for row in runbook["requests"]
            if row["status"] in {"approved", "in_progress"} and row["scheduled_for"] <= run_date
        ],
        key=lambda row: (row["scheduled_for"], row["tenant_id"], row["request_id"]),
    )

    for request in requests:
        request_id = str(request["request_id"])
        tenant_id = str(request["tenant_id"])
        tenant = tenants[tenant_id]
        active_holds = active_holds_by_tenant.get(tenant_id, [])
        preserve_exports = any(bool(hold.get("preserve_exports")) for hold in active_holds)

        if tenant["status"] not in {"offboarding", "hold_review", "closed"}:
            tenant["status"] = "offboarding"
            append_call(call_log, request_id, tenant_id, "mark_offboarding", tenant_id)

        for row in sorted(state["sessions.json"], key=lambda item: item["session_id"]):
            if row["tenant_id"] == tenant_id and row["status"] == "active":
                row["status"] = "revoked"
                append_call(call_log, request_id, tenant_id, "revoke_session", row["session_id"])
        for row in sorted(state["api_keys.json"], key=lambda item: item["key_id"]):
            if row["tenant_id"] == tenant_id and row["status"] == "active":
                row["status"] = "disabled"
                append_call(call_log, request_id, tenant_id, "disable_api_key", row["key_id"])
        for row in sorted(state["invites.json"], key=lambda item: item["invite_id"]):
            if row["tenant_id"] == tenant_id and row["status"] == "pending":
                row["status"] = "canceled"
                append_call(call_log, request_id, tenant_id, "cancel_invite", row["invite_id"])
        for row in sorted(state["memberships.json"], key=lambda item: item["membership_id"]):
            if (
                row["tenant_id"] == tenant_id
                and row["status"] == "active"
                and row["user_id"] != tenant["owner_user_id"]
            ):
                row["status"] = "disabled"
                append_call(call_log, request_id, tenant_id, "disable_membership", row["membership_id"])

        for row in sorted(state["integrations.json"], key=lambda item: item["integration_id"]):
            if row["tenant_id"] != tenant_id:
                continue
            if row["kind"] in {"webhook", "scim"} and row["status"] == "active":
                row["status"] = "disabled"
                append_call(call_log, request_id, tenant_id, "disable_integration", row["integration_id"])
            elif row["kind"] == "custom_domain" and row["status"] == "verified":
                if active_holds:
                    row["status"] = "hold_review"
                    append_call(call_log, request_id, tenant_id, "review_domain", row["integration_id"])
                else:
                    row["status"] = "parked"
                    append_call(call_log, request_id, tenant_id, "park_domain", row["integration_id"])

        for row in sorted(state["billing_accounts.json"], key=lambda item: item["billing_id"]):
            if row["tenant_id"] != tenant_id:
                continue
            if row["status"] == "active":
                if active_holds:
                    row["status"] = "locked_hold"
                    append_call(call_log, request_id, tenant_id, "hold_billing", row["billing_id"])
                else:
                    row["status"] = "closed"
                    append_call(call_log, request_id, tenant_id, "close_billing", row["billing_id"])
            if row["invoice_state"] in {"open", "past_due"} and not row.get("collection_lock"):
                row["collection_lock"] = True
                append_call(call_log, request_id, tenant_id, "lock_collections", row["billing_id"])

        for row in sorted(state["tickets.json"], key=lambda item: item["ticket_id"]):
            if row["tenant_id"] != tenant_id or row["status"] != "open":
                continue
            changed = False
            if row["assignee"] != "success-ops":
                row["assignee"] = "success-ops"
                changed = True
            tags = list(row.get("tags") or [])
            if "offboarding" not in tags:
                tags.append("offboarding")
                changed = True
            row["tags"] = sorted(set(tags))
            if changed:
                append_call(call_log, request_id, tenant_id, "queue_ticket", row["ticket_id"])

        for row in sorted(state["exports.json"], key=lambda item: item["export_id"]):
            if row["tenant_id"] != tenant_id:
                continue
            if row["status"] in {"running", "requested"}:
                if preserve_exports:
                    row["status"] = "retained_hold"
                    append_call(call_log, request_id, tenant_id, "retain_export", row["export_id"])
                else:
                    row["status"] = "canceled"
                    append_call(call_log, request_id, tenant_id, "cancel_export", row["export_id"])
            elif row["status"] == "complete" and row["retention_until"] < run_date:
                row["status"] = "expired"
                append_call(call_log, request_id, tenant_id, "expire_export", row["export_id"])

        final_status = "hold_review" if active_holds else "closed"
        if tenant["status"] != final_status:
            tenant["status"] = final_status
            append_call(call_log, request_id, tenant_id, "finalize_tenant", final_status)
        if request.get("status") != "completed" or request.get("completed_at") != run_date:
            request["status"] = "completed"
            request["completed_at"] = run_date
            append_call(call_log, request_id, tenant_id, "complete_request", request_id)

        audit_id = f"{request_id}:summary"
        state["audit_log.json"] = [
            row for row in state["audit_log.json"] if row.get("audit_id") != audit_id
        ]
        changed_operations = sum(
            1
            for row in call_log
            if row["request_id"] == request_id and row["tenant_id"] == tenant_id
        )
        state["audit_log.json"].append(
            {
                "audit_id": audit_id,
                "request_id": request_id,
                "tenant_id": tenant_id,
                "final_status": tenant["status"],
                "active_legal_hold": bool(active_holds),
                "changed_operations": changed_operations,
            }
        )
    state["audit_log.json"].sort(key=lambda row: row["audit_id"])
    return summary_from(state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", default="state")
    parser.add_argument("--output", default="output")
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    output_dir = Path(args.output)
    state = load_state(state_dir)
    summary = process(state)
    save_state(state_dir, state)
    write_json(output_dir / "offboarding_summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

python scripts/process_offboarding.py

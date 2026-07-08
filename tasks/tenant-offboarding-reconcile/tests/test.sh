#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


APP = Path(os.environ.get("APP_DIR", "/app"))
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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def load_state(state_dir: Path) -> dict[str, object]:
    return {name: read_json(state_dir / name) for name in STATE_FILES}


def save_state(state_dir: Path, state: dict[str, object]) -> None:
    for name in STATE_FILES:
        write_json(state_dir / name, state[name])


def seed_hidden(root: Path, *, variant: str) -> Path:
    state = root / variant
    state.mkdir()
    if variant == "hidden-a":
        data = {
            "runbook.json": {
                "run_date": "2026-09-05",
                "requests": [
                    {"request_id": "ha-1", "tenant_id": "north", "status": "approved", "scheduled_for": "2026-09-01", "requested_by": "ops"},
                    {"request_id": "ha-2", "tenant_id": "south", "status": "in_progress", "scheduled_for": "2026-09-05", "requested_by": "legal"},
                    {"request_id": "ha-3", "tenant_id": "west", "status": "approved", "scheduled_for": "2026-09-20", "requested_by": "ops"},
                ],
            },
            "tenants.json": [
                {"tenant_id": "north", "name": "North", "status": "active", "owner_user_id": "north-owner", "region": "us"},
                {"tenant_id": "south", "name": "South", "status": "active", "owner_user_id": "south-owner", "region": "eu"},
                {"tenant_id": "west", "name": "West", "status": "active", "owner_user_id": "west-owner", "region": "us"},
            ],
            "memberships.json": [
                {"membership_id": "mn-o", "tenant_id": "north", "user_id": "north-owner", "role": "owner", "status": "active", "user_type": "employee"},
                {"membership_id": "mn-1", "tenant_id": "north", "user_id": "north-1", "role": "admin", "status": "active", "user_type": "employee"},
                {"membership_id": "ms-o", "tenant_id": "south", "user_id": "south-owner", "role": "owner", "status": "active", "user_type": "employee"},
                {"membership_id": "ms-1", "tenant_id": "south", "user_id": "south-1", "role": "member", "status": "active", "user_type": "contractor"},
            ],
            "sessions.json": [
                {"session_id": "sn-1", "tenant_id": "north", "user_id": "north-1", "status": "active"},
                {"session_id": "ss-1", "tenant_id": "south", "user_id": "south-1", "status": "active"},
            ],
            "api_keys.json": [
                {"key_id": "kn-1", "tenant_id": "north", "owner_type": "service", "status": "active"},
                {"key_id": "ks-1", "tenant_id": "south", "owner_type": "service", "status": "disabled"},
            ],
            "invites.json": [
                {"invite_id": "in-1", "tenant_id": "north", "status": "pending"},
                {"invite_id": "is-1", "tenant_id": "south", "status": "pending"},
            ],
            "exports.json": [
                {"export_id": "en-1", "tenant_id": "north", "status": "requested", "retention_until": "2026-09-30"},
                {"export_id": "en-2", "tenant_id": "north", "status": "complete", "retention_until": "2026-08-01"},
                {"export_id": "es-1", "tenant_id": "south", "status": "running", "retention_until": "2026-10-01"},
            ],
            "tickets.json": [
                {"ticket_id": "tn-1", "tenant_id": "north", "status": "open", "assignee": "tier1", "tags": []},
                {"ticket_id": "ts-1", "tenant_id": "south", "status": "open", "assignee": "legal", "tags": ["offboarding"]},
            ],
            "integrations.json": [
                {"integration_id": "in-domain", "tenant_id": "north", "kind": "custom_domain", "status": "verified"},
                {"integration_id": "in-webhook", "tenant_id": "north", "kind": "webhook", "status": "active"},
                {"integration_id": "is-domain", "tenant_id": "south", "kind": "custom_domain", "status": "verified"},
                {"integration_id": "is-scim", "tenant_id": "south", "kind": "scim", "status": "active"},
            ],
            "billing_accounts.json": [
                {"billing_id": "bn-1", "tenant_id": "north", "status": "active", "invoice_state": "open", "collection_lock": False},
                {"billing_id": "bs-1", "tenant_id": "south", "status": "active", "invoice_state": "past_due", "collection_lock": False},
            ],
            "legal_holds.json": [
                {"hold_id": "hold-south", "tenant_id": "south", "status": "active", "preserve_exports": True, "reason": "litigation"}
            ],
            "call_log.json": [],
            "audit_log.json": [],
        }
    else:
        data = {
            "runbook.json": {
                "run_date": "2026-11-10",
                "requests": [
                    {"request_id": "hb-1", "tenant_id": "orchid", "status": "approved", "scheduled_for": "2026-11-09", "requested_by": "ops"},
                    {"request_id": "hb-2", "tenant_id": "pine", "status": "completed", "scheduled_for": "2026-11-01", "requested_by": "ops"},
                    {"request_id": "hb-3", "tenant_id": "quartz", "status": "approved", "scheduled_for": "2026-11-10", "requested_by": "ops"},
                ],
            },
            "tenants.json": [
                {"tenant_id": "orchid", "name": "Orchid", "status": "offboarding", "owner_user_id": "orchid-owner", "region": "us"},
                {"tenant_id": "pine", "name": "Pine", "status": "closed", "owner_user_id": "pine-owner", "region": "us"},
                {"tenant_id": "quartz", "name": "Quartz", "status": "active", "owner_user_id": "quartz-owner", "region": "eu"},
            ],
            "memberships.json": [
                {"membership_id": "mo-o", "tenant_id": "orchid", "user_id": "orchid-owner", "role": "owner", "status": "active", "user_type": "employee"},
                {"membership_id": "mo-1", "tenant_id": "orchid", "user_id": "orchid-1", "role": "member", "status": "disabled", "user_type": "employee"},
                {"membership_id": "mq-o", "tenant_id": "quartz", "user_id": "quartz-owner", "role": "owner", "status": "active", "user_type": "employee"},
                {"membership_id": "mq-1", "tenant_id": "quartz", "user_id": "quartz-1", "role": "member", "status": "active", "user_type": "employee"},
            ],
            "sessions.json": [
                {"session_id": "so-1", "tenant_id": "orchid", "user_id": "orchid-owner", "status": "revoked"},
                {"session_id": "sq-1", "tenant_id": "quartz", "user_id": "quartz-1", "status": "active"},
            ],
            "api_keys.json": [
                {"key_id": "ko-1", "tenant_id": "orchid", "owner_type": "service", "status": "active"},
                {"key_id": "kq-1", "tenant_id": "quartz", "owner_type": "service", "status": "active"},
            ],
            "invites.json": [
                {"invite_id": "iq-1", "tenant_id": "quartz", "status": "pending"}
            ],
            "exports.json": [
                {"export_id": "eo-1", "tenant_id": "orchid", "status": "complete", "retention_until": "2026-10-01"},
                {"export_id": "eq-1", "tenant_id": "quartz", "status": "running", "retention_until": "2026-11-30"},
            ],
            "tickets.json": [
                {"ticket_id": "to-1", "tenant_id": "orchid", "status": "open", "assignee": "success-ops", "tags": ["offboarding"]},
                {"ticket_id": "tq-1", "tenant_id": "quartz", "status": "open", "assignee": "tier1", "tags": ["urgent"]},
            ],
            "integrations.json": [
                {"integration_id": "io-domain", "tenant_id": "orchid", "kind": "custom_domain", "status": "parked"},
                {"integration_id": "io-webhook", "tenant_id": "orchid", "kind": "webhook", "status": "active"},
                {"integration_id": "iq-domain", "tenant_id": "quartz", "kind": "custom_domain", "status": "verified"},
                {"integration_id": "iq-scim", "tenant_id": "quartz", "kind": "scim", "status": "active"},
            ],
            "billing_accounts.json": [
                {"billing_id": "bo-1", "tenant_id": "orchid", "status": "active", "invoice_state": "paid", "collection_lock": False},
                {"billing_id": "bq-1", "tenant_id": "quartz", "status": "active", "invoice_state": "open", "collection_lock": False},
            ],
            "legal_holds.json": [
                {"hold_id": "hold-quartz", "tenant_id": "quartz", "status": "active", "preserve_exports": False, "reason": "do not preserve exports"}
            ],
            "call_log.json": [
                {"request_id": "hb-1", "tenant_id": "orchid", "action": "disable_membership", "target_id": "mo-1", "sequence": 7}
            ],
            "audit_log.json": [
                {"audit_id": "hb-old:summary", "request_id": "hb-old", "tenant_id": "old", "final_status": "closed", "active_legal_hold": False, "changed_operations": 0}
            ],
        }
    for name, value in data.items():
        write_json(state / name, value)
    return state


def append_call(call_log: list[dict[str, object]], request_id: str, tenant_id: str, action: str, target_id: str) -> None:
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


def expected_from(initial: dict[str, object]) -> tuple[dict[str, object], dict[str, int]]:
    state = deepcopy(initial)
    runbook = state["runbook.json"]
    run_date = runbook["run_date"]
    call_log = state["call_log.json"]
    tenants = {row["tenant_id"]: row for row in state["tenants.json"]}
    holds_by_tenant: dict[str, list[dict[str, object]]] = {}
    for hold in state["legal_holds.json"]:
        if hold["status"] == "active":
            holds_by_tenant.setdefault(hold["tenant_id"], []).append(hold)

    requests = sorted(
        [
            row
            for row in runbook["requests"]
            if row["status"] in {"approved", "in_progress"} and row["scheduled_for"] <= run_date
        ],
        key=lambda row: (row["scheduled_for"], row["tenant_id"], row["request_id"]),
    )
    for request in requests:
        request_id = request["request_id"]
        tenant_id = request["tenant_id"]
        tenant = tenants[tenant_id]
        active_holds = holds_by_tenant.get(tenant_id, [])
        preserve_exports = any(bool(row.get("preserve_exports")) for row in active_holds)
        if tenant["status"] not in {"offboarding", "hold_review", "closed"}:
            tenant["status"] = "offboarding"
            append_call(call_log, request_id, tenant_id, "mark_offboarding", tenant_id)

        for row in sorted(state["sessions.json"], key=lambda row: row["session_id"]):
            if row["tenant_id"] == tenant_id and row["status"] == "active":
                row["status"] = "revoked"
                append_call(call_log, request_id, tenant_id, "revoke_session", row["session_id"])
        for row in sorted(state["api_keys.json"], key=lambda row: row["key_id"]):
            if row["tenant_id"] == tenant_id and row["status"] == "active":
                row["status"] = "disabled"
                append_call(call_log, request_id, tenant_id, "disable_api_key", row["key_id"])
        for row in sorted(state["invites.json"], key=lambda row: row["invite_id"]):
            if row["tenant_id"] == tenant_id and row["status"] == "pending":
                row["status"] = "canceled"
                append_call(call_log, request_id, tenant_id, "cancel_invite", row["invite_id"])
        for row in sorted(state["memberships.json"], key=lambda row: row["membership_id"]):
            if (
                row["tenant_id"] == tenant_id
                and row["status"] == "active"
                and row["user_id"] != tenant["owner_user_id"]
            ):
                row["status"] = "disabled"
                append_call(call_log, request_id, tenant_id, "disable_membership", row["membership_id"])

        for row in sorted(state["integrations.json"], key=lambda row: row["integration_id"]):
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

        for row in sorted(state["billing_accounts.json"], key=lambda row: row["billing_id"]):
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

        for row in sorted(state["tickets.json"], key=lambda row: row["ticket_id"]):
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

        for row in sorted(state["exports.json"], key=lambda row: row["export_id"]):
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
    summary = summary_from(state)
    return state, summary


def summary_from(state: dict[str, object]) -> dict[str, int]:
    run_date = state["runbook.json"]["run_date"]
    requests = state["runbook.json"]["requests"]
    tenants = state["tenants.json"]
    call_log = state["call_log.json"]
    counts: dict[str, int] = {}
    for row in call_log:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    return {
        "processed_requests": sum(
            1 for row in requests if row.get("status") == "completed" and row.get("completed_at") == run_date
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


def run_script(state_dir: Path, output_dir: Path) -> None:
    script = APP / "scripts" / "process_offboarding.py"
    if not script.exists():
        raise AssertionError("missing scripts/process_offboarding.py")
    subprocess.run(
        [sys.executable, str(script), "--state-dir", str(state_dir), "--output", str(output_dir)],
        cwd=APP,
        text=True,
        check=True,
    )


def assert_state(testcase: unittest.TestCase, state_dir: Path, initial: dict[str, object], output_dir: Path) -> None:
    expected_state, expected_summary = expected_from(initial)
    actual_state = load_state(state_dir)
    testcase.assertEqual(canonical_state(actual_state), canonical_state(expected_state))
    testcase.assertEqual(read_json(output_dir / "offboarding_summary.json"), expected_summary)
    seen = set()
    sequences = []
    for row in actual_state["call_log.json"]:
        key = (row["request_id"], row["tenant_id"], row["action"], row["target_id"])
        testcase.assertNotIn(key, seen)
        seen.add(key)
        sequences.append(int(row["sequence"]))
    testcase.assertEqual(sequences, sorted(sequences))
    testcase.assertEqual(len(sequences), len(set(sequences)))


def canonical_state(state: dict[str, object]) -> dict[str, object]:
    canonical = deepcopy(state)
    canonical["runbook.json"]["requests"] = sorted(
        canonical["runbook.json"]["requests"], key=lambda row: row["request_id"]
    )
    canonical["tenants.json"] = sorted(canonical["tenants.json"], key=lambda row: row["tenant_id"])
    canonical["memberships.json"] = sorted(
        canonical["memberships.json"], key=lambda row: row["membership_id"]
    )
    canonical["sessions.json"] = sorted(canonical["sessions.json"], key=lambda row: row["session_id"])
    canonical["api_keys.json"] = sorted(canonical["api_keys.json"], key=lambda row: row["key_id"])
    canonical["invites.json"] = sorted(canonical["invites.json"], key=lambda row: row["invite_id"])
    canonical["exports.json"] = sorted(canonical["exports.json"], key=lambda row: row["export_id"])
    for ticket in canonical["tickets.json"]:
        ticket["tags"] = sorted(ticket.get("tags") or [])
    canonical["tickets.json"] = sorted(canonical["tickets.json"], key=lambda row: row["ticket_id"])
    canonical["integrations.json"] = sorted(
        canonical["integrations.json"], key=lambda row: row["integration_id"]
    )
    canonical["billing_accounts.json"] = sorted(
        canonical["billing_accounts.json"], key=lambda row: row["billing_id"]
    )
    canonical["legal_holds.json"] = sorted(
        canonical["legal_holds.json"], key=lambda row: row["hold_id"]
    )
    canonical["audit_log.json"] = sorted(
        canonical["audit_log.json"], key=lambda row: row["audit_id"]
    )
    canonical["call_log.json"] = sorted(canonical["call_log.json"], key=lambda row: row["sequence"])
    return canonical


class TenantOffboardingVerifier(unittest.TestCase):
    def check_state(self, state_dir: Path) -> None:
        initial = load_state(state_dir)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            run_script(state_dir, output)
            assert_state(self, state_dir, initial, output)
            after_first_state = load_state(state_dir)
            after_first_output = read_json(output / "offboarding_summary.json")
            run_script(state_dir, output)
            self.assertEqual(load_state(state_dir), after_first_state)
            self.assertEqual(read_json(output / "offboarding_summary.json"), after_first_output)

    def test_visible_state(self) -> None:
        self.check_state(APP / "state")

    def test_hidden_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.check_state(seed_hidden(root, variant="hidden-a"))
            self.check_state(seed_hidden(root, variant="hidden-b"))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TenantOffboardingVerifier)
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

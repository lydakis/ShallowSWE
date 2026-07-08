from __future__ import annotations

from pathlib import Path
import json
import sys
import textwrap


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def write_json(root: Path, relative: str, value: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)
    write(
        root,
        "README.md",
        """
        # Tenant Operations

        Synthetic tenant operations state store used for offboarding runbook reconciliation.
        Implement the runbook in `scripts/process_offboarding.py`.
        """,
    )
    write(root, "workspace_ops/__init__.py", "")
    write(
        root,
        "workspace_ops/store.py",
        """
        from __future__ import annotations

        from pathlib import Path
        import json


        def read_json(root: str | Path, name: str) -> object:
            return json.loads((Path(root) / name).read_text())


        def write_json(root: str | Path, name: str, value: object) -> None:
            path = Path(root) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\\n")
        """,
    )
    for index in range(1, 91):
        write(
            root,
            f"workspace_ops/generated/noise_{index:02d}.py",
            f"""
            from __future__ import annotations

            MARKER = "tenant-offboarding-noise-{index:02d}"


            def marker(value: object) -> str:
                return f"{{MARKER}}:{{value}}"
            """,
        )

    state = root / "state"
    write_json(
        state,
        "runbook.json",
        {
            "run_date": "2026-07-07",
            "requests": [
                {"request_id": "req-100", "tenant_id": "tenant-alpha", "status": "approved", "scheduled_for": "2026-07-07", "requested_by": "ops"},
                {"request_id": "req-101", "tenant_id": "tenant-beta", "status": "approved", "scheduled_for": "2026-07-06", "requested_by": "legal"},
                {"request_id": "req-102", "tenant_id": "tenant-gamma", "status": "approved", "scheduled_for": "2026-07-20", "requested_by": "ops"},
                {"request_id": "req-103", "tenant_id": "tenant-delta", "status": "completed", "scheduled_for": "2026-07-01", "requested_by": "ops"},
            ],
        },
    )
    write_json(
        state,
        "tenants.json",
        [
            {"tenant_id": "tenant-alpha", "name": "Alpha Labs", "status": "active", "owner_user_id": "alpha-owner", "region": "us"},
            {"tenant_id": "tenant-beta", "name": "Beta Health", "status": "offboarding", "owner_user_id": "beta-owner", "region": "eu"},
            {"tenant_id": "tenant-gamma", "name": "Gamma Retail", "status": "active", "owner_user_id": "gamma-owner", "region": "us"},
            {"tenant_id": "tenant-delta", "name": "Delta School", "status": "closed", "owner_user_id": "delta-owner", "region": "us"},
        ],
    )
    write_json(
        state,
        "memberships.json",
        [
            {"membership_id": "m-alpha-owner", "tenant_id": "tenant-alpha", "user_id": "alpha-owner", "role": "owner", "status": "active", "user_type": "employee"},
            {"membership_id": "m-alpha-1", "tenant_id": "tenant-alpha", "user_id": "alpha-1", "role": "admin", "status": "active", "user_type": "employee"},
            {"membership_id": "m-alpha-2", "tenant_id": "tenant-alpha", "user_id": "alpha-2", "role": "member", "status": "active", "user_type": "contractor"},
            {"membership_id": "m-beta-owner", "tenant_id": "tenant-beta", "user_id": "beta-owner", "role": "owner", "status": "active", "user_type": "employee"},
            {"membership_id": "m-beta-1", "tenant_id": "tenant-beta", "user_id": "beta-1", "role": "member", "status": "disabled", "user_type": "employee"},
            {"membership_id": "m-gamma-1", "tenant_id": "tenant-gamma", "user_id": "gamma-1", "role": "member", "status": "active", "user_type": "employee"},
        ],
    )
    write_json(
        state,
        "sessions.json",
        [
            {"session_id": "s-alpha-1", "tenant_id": "tenant-alpha", "user_id": "alpha-1", "status": "active"},
            {"session_id": "s-alpha-2", "tenant_id": "tenant-alpha", "user_id": "alpha-2", "status": "revoked"},
            {"session_id": "s-beta-1", "tenant_id": "tenant-beta", "user_id": "beta-owner", "status": "active"},
            {"session_id": "s-gamma-1", "tenant_id": "tenant-gamma", "user_id": "gamma-1", "status": "active"},
        ],
    )
    write_json(
        state,
        "api_keys.json",
        [
            {"key_id": "k-alpha-1", "tenant_id": "tenant-alpha", "owner_type": "service", "status": "active"},
            {"key_id": "k-alpha-2", "tenant_id": "tenant-alpha", "owner_type": "user", "status": "disabled"},
            {"key_id": "k-beta-1", "tenant_id": "tenant-beta", "owner_type": "service", "status": "active"},
            {"key_id": "k-gamma-1", "tenant_id": "tenant-gamma", "owner_type": "service", "status": "active"},
        ],
    )
    write_json(
        state,
        "invites.json",
        [
            {"invite_id": "i-alpha-1", "tenant_id": "tenant-alpha", "status": "pending"},
            {"invite_id": "i-alpha-2", "tenant_id": "tenant-alpha", "status": "accepted"},
            {"invite_id": "i-beta-1", "tenant_id": "tenant-beta", "status": "pending"},
            {"invite_id": "i-gamma-1", "tenant_id": "tenant-gamma", "status": "pending"},
        ],
    )
    write_json(
        state,
        "exports.json",
        [
            {"export_id": "e-alpha-1", "tenant_id": "tenant-alpha", "status": "running", "retention_until": "2026-07-20"},
            {"export_id": "e-alpha-2", "tenant_id": "tenant-alpha", "status": "complete", "retention_until": "2026-07-01"},
            {"export_id": "e-beta-1", "tenant_id": "tenant-beta", "status": "running", "retention_until": "2026-08-01"},
            {"export_id": "e-gamma-1", "tenant_id": "tenant-gamma", "status": "running", "retention_until": "2026-08-01"},
        ],
    )
    write_json(
        state,
        "tickets.json",
        [
            {"ticket_id": "t-alpha-1", "tenant_id": "tenant-alpha", "status": "open", "assignee": "tier1", "tags": ["billing"]},
            {"ticket_id": "t-alpha-2", "tenant_id": "tenant-alpha", "status": "closed", "assignee": "tier1", "tags": []},
            {"ticket_id": "t-beta-1", "tenant_id": "tenant-beta", "status": "open", "assignee": "success-ops", "tags": ["offboarding"]},
            {"ticket_id": "t-gamma-1", "tenant_id": "tenant-gamma", "status": "open", "assignee": "tier1", "tags": []},
        ],
    )
    write_json(
        state,
        "integrations.json",
        [
            {"integration_id": "int-alpha-domain", "tenant_id": "tenant-alpha", "kind": "custom_domain", "status": "verified"},
            {"integration_id": "int-alpha-webhook", "tenant_id": "tenant-alpha", "kind": "webhook", "status": "active"},
            {"integration_id": "int-beta-domain", "tenant_id": "tenant-beta", "kind": "custom_domain", "status": "verified"},
            {"integration_id": "int-beta-scim", "tenant_id": "tenant-beta", "kind": "scim", "status": "active"},
            {"integration_id": "int-gamma-webhook", "tenant_id": "tenant-gamma", "kind": "webhook", "status": "active"},
        ],
    )
    write_json(
        state,
        "billing_accounts.json",
        [
            {"billing_id": "bill-alpha", "tenant_id": "tenant-alpha", "status": "active", "invoice_state": "open", "collection_lock": False},
            {"billing_id": "bill-beta", "tenant_id": "tenant-beta", "status": "active", "invoice_state": "past_due", "collection_lock": False},
            {"billing_id": "bill-gamma", "tenant_id": "tenant-gamma", "status": "active", "invoice_state": "open", "collection_lock": False},
            {"billing_id": "bill-delta", "tenant_id": "tenant-delta", "status": "closed", "invoice_state": "paid", "collection_lock": True},
        ],
    )
    write_json(
        state,
        "legal_holds.json",
        [
            {"hold_id": "hold-beta", "tenant_id": "tenant-beta", "status": "active", "preserve_exports": True, "reason": "regulatory request"},
            {"hold_id": "hold-alpha-old", "tenant_id": "tenant-alpha", "status": "released", "preserve_exports": True, "reason": "old matter"},
        ],
    )
    write_json(
        state,
        "call_log.json",
        [
            {"request_id": "req-101", "tenant_id": "tenant-beta", "action": "disable_membership", "target_id": "m-beta-1", "sequence": 1}
        ],
    )
    write_json(state, "audit_log.json", [])


if __name__ == "__main__":
    main()

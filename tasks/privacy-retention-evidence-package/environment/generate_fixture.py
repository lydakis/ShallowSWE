from __future__ import annotations

from pathlib import Path
import csv
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


def write_csv(root: Path, relative: str, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def service_source(root: Path, system_id: str, relative: str, body: str) -> None:
    write(root, f"services/{system_id}/src/{relative}", body)
    for index in range(1, 22):
        write(
            root,
            f"services/{system_id}/src/generated/noise_{index:02d}.py",
            f"""
            from __future__ import annotations

            SYSTEM_ID = {system_id!r}
            NOISE_INDEX = {index}

            def marker(seed: int) -> str:
                return f"{{SYSTEM_ID}}:{{NOISE_INDEX}}:{{seed % 23}}"
            """,
        )


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)

    write(
        root,
        "README.md",
        """
        # Synthetic Privacy Platform Repo

        Repository used for a data-retention evidence package. Catalogs, purge/export jobs, legal
        holds, downstream dataset lineage, incidents, exemptions, and source annotations are
        intentionally inconsistent.
        """,
    )
    write_json(
        root,
        "catalog/systems.json",
        [
            {"system_id": "identity", "display_name": "Identity", "owner_team": "platform", "tier": 1},
            {"system_id": "support", "display_name": "Support", "owner_team": "care", "tier": 2},
            {"system_id": "billing", "display_name": "Billing", "owner_team": "finance", "tier": 1},
            {"system_id": "analytics", "display_name": "Analytics", "owner_team": "data", "tier": 2},
            {"system_id": "marketing", "display_name": "Marketing", "owner_team": "growth", "tier": 3},
        ],
    )
    write_csv(
        root,
        "catalog/datasets.csv",
        [
            {"dataset_id": "identity.users", "system_id": "identity", "owner_team": "platform", "classification": "pii", "subject_type": "customer", "retention_days": 540, "deletion_mode": "hard_delete", "storage_path": "s3://privacy/identity/users"},
            {"dataset_id": "identity.sessions", "system_id": "identity", "owner_team": "platform", "classification": "operational", "subject_type": "customer", "retention_days": 45, "deletion_mode": "ttl", "storage_path": "redis://identity/sessions"},
            {"dataset_id": "support.tickets", "system_id": "support", "owner_team": "care", "classification": "sensitive", "subject_type": "customer", "retention_days": 730, "deletion_mode": "hard_delete", "storage_path": "postgres://support/tickets"},
            {"dataset_id": "billing.invoices", "system_id": "billing", "owner_team": "finance", "classification": "financial", "subject_type": "customer", "retention_days": 2555, "deletion_mode": "archive", "storage_path": "s3://finance/invoices"},
            {"dataset_id": "analytics.events", "system_id": "analytics", "owner_team": "data", "classification": "pseudonymous", "subject_type": "customer", "retention_days": 400, "deletion_mode": "partition_drop", "storage_path": "warehouse.analytics.events"},
            {"dataset_id": "marketing.leads", "system_id": "marketing", "owner_team": "growth", "classification": "pii", "subject_type": "prospect", "retention_days": 365, "deletion_mode": "hard_delete", "storage_path": "crm://marketing/leads"},
            {"dataset_id": "support.macros", "system_id": "support", "owner_team": "care", "classification": "public", "subject_type": "none", "retention_days": 3650, "deletion_mode": "none", "storage_path": "postgres://support/macros"},
        ],
        ["dataset_id", "system_id", "owner_team", "classification", "subject_type", "retention_days", "deletion_mode", "storage_path"],
    )
    write_json(
        root,
        "policies/retention_policy.json",
        {
            "report_date": "2026-07-07",
            "classification_retention_days": {
                "pii": 365,
                "sensitive": 540,
                "financial": 2555,
                "pseudonymous": 180,
                "operational": 90,
                "public": 3650,
            },
            "stale_job_days": 14,
            "export_job_stale_days": 30,
            "propagation_required_classifications": ["pii", "sensitive", "pseudonymous"],
            "due_days": {
                "blocked": 1,
                "needs_work": 7,
                "accepted_risk": 14,
                "ready": 30,
            },
            "action_order": [
                "retention_limit",
                "purge_job",
                "purge_job_current",
                "subject_export",
                "downstream_delete",
                "downstream_export",
                "source_reference",
                "open_incident",
                "legal_hold",
            ],
        },
    )
    write_csv(
        root,
        "jobs/purge_jobs.csv",
        [
            {"job_id": "purge-identity-users", "dataset_id": "identity.users", "mode": "hard_delete", "schedule_days": 30, "last_success_at": "2026-06-15", "filter_expr": "created_at < cutoff"},
            {"job_id": "purge-identity-sessions", "dataset_id": "identity.sessions", "mode": "ttl", "schedule_days": 1, "last_success_at": "2026-07-06", "filter_expr": "expires_at < now"},
            {"job_id": "purge-support-tickets", "dataset_id": "support.tickets", "mode": "hard_delete", "schedule_days": 30, "last_success_at": "2026-06-01", "filter_expr": "closed_at < cutoff"},
            {"job_id": "archive-billing-invoices", "dataset_id": "billing.invoices", "mode": "archive", "schedule_days": 30, "last_success_at": "2026-07-01", "filter_expr": "invoice_date < cutoff"},
            {"job_id": "drop-analytics-events", "dataset_id": "analytics.events", "mode": "partition_drop", "schedule_days": 7, "last_success_at": "2026-07-03", "filter_expr": "event_date < cutoff"},
            {"job_id": "purge-marketing-leads", "dataset_id": "marketing.leads", "mode": "soft_delete", "schedule_days": 14, "last_success_at": "2026-06-20", "filter_expr": "created_at < cutoff"},
        ],
        ["job_id", "dataset_id", "mode", "schedule_days", "last_success_at", "filter_expr"],
    )
    write_csv(
        root,
        "jobs/export_jobs.csv",
        [
            {"job_id": "export-identity-users", "dataset_id": "identity.users", "last_success_at": "2026-07-05", "scope": "subject"},
            {"job_id": "export-support-tickets", "dataset_id": "support.tickets", "last_success_at": "2026-05-01", "scope": "subject"},
            {"job_id": "export-billing-invoices", "dataset_id": "billing.invoices", "last_success_at": "2026-07-02", "scope": "subject"},
            {"job_id": "export-analytics-events", "dataset_id": "analytics.events", "last_success_at": "2026-07-03", "scope": "aggregate"},
        ],
        ["job_id", "dataset_id", "last_success_at", "scope"],
    )
    write_csv(
        root,
        "legal/holds.csv",
        [
            {"hold_id": "hold-001", "dataset_id": "billing.invoices", "status": "active", "expires_on": "2026-12-31", "reason": "tax audit"},
            {"hold_id": "hold-002", "dataset_id": "support.tickets", "status": "expired", "expires_on": "2026-06-30", "reason": "support dispute"},
            {"hold_id": "hold-003", "dataset_id": "identity.users", "status": "active", "expires_on": "2026-07-20", "reason": "privacy request review"},
        ],
        ["hold_id", "dataset_id", "status", "expires_on", "reason"],
    )
    write_csv(
        root,
        "lineage/downstream_edges.csv",
        [
            {"source_dataset_id": "identity.users", "target_dataset_id": "analytics.events", "delete_propagates": "false", "export_propagates": "true"},
            {"source_dataset_id": "support.tickets", "target_dataset_id": "analytics.events", "delete_propagates": "false", "export_propagates": "false"},
            {"source_dataset_id": "billing.invoices", "target_dataset_id": "analytics.events", "delete_propagates": "true", "export_propagates": "true"},
            {"source_dataset_id": "marketing.leads", "target_dataset_id": "analytics.events", "delete_propagates": "true", "export_propagates": "false"},
        ],
        ["source_dataset_id", "target_dataset_id", "delete_propagates", "export_propagates"],
    )
    write_csv(
        root,
        "incidents/data_incidents.csv",
        [
            {"dataset_id": "support.tickets", "severity": "P1", "status": "open", "opened_at": "2026-07-06"},
            {"dataset_id": "analytics.events", "severity": "P2", "status": "open", "opened_at": "2026-07-01"},
            {"dataset_id": "identity.users", "severity": "P0", "status": "resolved", "opened_at": "2026-06-15"},
        ],
        ["dataset_id", "severity", "status", "opened_at"],
    )
    write_csv(
        root,
        "exemptions/retention_exemptions.csv",
        [
            {"dataset_id": "analytics.events", "control": "retention_limit", "expires_on": "2026-08-01", "reason": "warehouse migration"},
            {"dataset_id": "support.tickets", "control": "subject_export", "expires_on": "2026-06-30", "reason": "legacy export"},
            {"dataset_id": "marketing.leads", "control": "downstream_export", "expires_on": "2026-07-31", "reason": "crm connector migration"},
        ],
        ["dataset_id", "control", "expires_on", "reason"],
    )

    service_source(
        root,
        "identity",
        "users.py",
        """
        # dataset: identity.users
        def delete_user(user_id):
            purge_dataset("identity.users", mode="hard_delete")

        # dataset: identity.sessions
        def expire_session(session_id):
            purge_dataset("identity.sessions", mode="ttl")
        """,
    )
    service_source(
        root,
        "support",
        "tickets.py",
        """
        # dataset: support.tickets
        def close_ticket(ticket_id):
            record_dataset("support.tickets")
        """,
    )
    service_source(
        root,
        "billing",
        "invoices.py",
        """
        # dataset: billing.invoices
        def archive_invoice(invoice_id):
            archive_dataset("billing.invoices")
        """,
    )
    service_source(
        root,
        "analytics",
        "events.py",
        """
        # dataset: analytics.events
        def drop_old_events(cutoff):
            partition_drop("analytics.events", cutoff)
        """,
    )
    service_source(
        root,
        "marketing",
        "leads.py",
        """
        # dataset: marketing.leads
        def ingest_lead(payload):
            record_dataset("marketing.leads")
        """,
    )


if __name__ == "__main__":
    main()

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


def integration_source(root: Path, vendor_id: str, relative: str, body: str) -> None:
    write(root, f"integrations/{vendor_id}/src/{relative}", body)
    for index in range(1, 20):
        write(
            root,
            f"integrations/{vendor_id}/src/generated/noise_{index:02d}.py",
            f"""
            from __future__ import annotations

            VENDOR = {vendor_id!r}
            NOISE_INDEX = {index}

            def marker(seed: int) -> str:
                return f"{{VENDOR}}:{{NOISE_INDEX}}:{{seed % 31}}"
            """,
        )


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)

    write(
        root,
        "README.md",
        """
        # Synthetic Vendor Risk Repository

        Repository used for a vendor-risk evidence package. Vendor inventory, production services,
        contracts, security evidence, subprocessors, incidents, exceptions, and source annotations
        are intentionally inconsistent.
        """,
    )
    write_json(
        root,
        "policies/vendor_risk_policy.json",
        {
            "report_date": "2026-07-07",
            "renewal_window_days": 45,
            "current_evidence_types": ["soc2", "pentest"],
            "required_evidence_by_criticality": {
                "critical": ["soc2", "pentest"],
                "high": ["soc2"],
                "medium": [],
                "low": [],
            },
            "dpa_required_data_classes": ["pii", "sensitive", "financial"],
            "regional_review_regions": ["CN", "RU"],
            "regional_review_data_classes": ["pii", "sensitive", "financial"],
            "due_days": {
                "blocked": 3,
                "needs_work": 14,
                "accepted_risk": 30,
                "ready": 60,
            },
            "action_order": [
                "dpa",
                "soc2_current",
                "pentest_current",
                "subprocessor_approval",
                "regional_review",
                "production_source_reference",
                "open_incident",
                "renewal_review",
                "accepted_exception",
            ],
        },
    )
    write_csv(
        root,
        "inventory/vendors.csv",
        [
            {"vendor_id": "authzero", "owner_team": "platform", "criticality": "critical", "data_classification": "pii", "renewal_date": "2026-08-01", "status": "active", "contract_id": "c-authzero"},
            {"vendor_id": "payflow", "owner_team": "finance", "criticality": "critical", "data_classification": "financial", "renewal_date": "2026-09-15", "status": "active", "contract_id": "c-payflow"},
            {"vendor_id": "chatly", "owner_team": "care", "criticality": "high", "data_classification": "sensitive", "renewal_date": "2026-07-25", "status": "active", "contract_id": "c-chatly"},
            {"vendor_id": "marketbee", "owner_team": "growth", "criticality": "medium", "data_classification": "pii", "renewal_date": "2026-10-30", "status": "active", "contract_id": "c-marketbee"},
            {"vendor_id": "loglake", "owner_team": "data", "criticality": "high", "data_classification": "pseudonymous", "renewal_date": "2026-09-20", "status": "active", "contract_id": "c-loglake"},
            {"vendor_id": "docsbox", "owner_team": "docs", "criticality": "low", "data_classification": "public", "renewal_date": "2027-01-01", "status": "active", "contract_id": "c-docsbox"},
        ],
        ["vendor_id", "owner_team", "criticality", "data_classification", "renewal_date", "status", "contract_id"],
    )
    write_json(
        root,
        "inventory/services.json",
        [
            {"service_id": "sso", "vendor_id": "authzero", "owner_team": "platform", "production": True, "data_types": ["pii", "credentials"]},
            {"service_id": "payments", "vendor_id": "payflow", "owner_team": "finance", "production": True, "data_types": ["financial"]},
            {"service_id": "support-chat", "vendor_id": "chatly", "owner_team": "care", "production": True, "data_types": ["sensitive"]},
            {"service_id": "lead-sync", "vendor_id": "marketbee", "owner_team": "growth", "production": False, "data_types": ["pii"]},
            {"service_id": "analytics-log", "vendor_id": "loglake", "owner_team": "data", "production": True, "data_types": ["pseudonymous"]},
            {"service_id": "docs-search", "vendor_id": "docsbox", "owner_team": "docs", "production": False, "data_types": ["public"]},
        ],
    )
    write_csv(
        root,
        "contracts/contracts.csv",
        [
            {"contract_id": "c-authzero", "vendor_id": "authzero", "dpa_signed": "false", "subprocessor_notice_days": 15, "termination_days": 30},
            {"contract_id": "c-payflow", "vendor_id": "payflow", "dpa_signed": "true", "subprocessor_notice_days": 30, "termination_days": 60},
            {"contract_id": "c-chatly", "vendor_id": "chatly", "dpa_signed": "true", "subprocessor_notice_days": 7, "termination_days": 30},
            {"contract_id": "c-marketbee", "vendor_id": "marketbee", "dpa_signed": "true", "subprocessor_notice_days": 30, "termination_days": 30},
            {"contract_id": "c-loglake", "vendor_id": "loglake", "dpa_signed": "true", "subprocessor_notice_days": 14, "termination_days": 30},
            {"contract_id": "c-docsbox", "vendor_id": "docsbox", "dpa_signed": "false", "subprocessor_notice_days": 0, "termination_days": 0},
        ],
        ["contract_id", "vendor_id", "dpa_signed", "subprocessor_notice_days", "termination_days"],
    )
    write_csv(
        root,
        "security/evidence.csv",
        [
            {"vendor_id": "authzero", "evidence_type": "soc2", "status": "current", "issued_on": "2026-01-10", "expires_on": "2027-01-10"},
            {"vendor_id": "authzero", "evidence_type": "pentest", "status": "current", "issued_on": "2025-01-01", "expires_on": "2026-01-01"},
            {"vendor_id": "payflow", "evidence_type": "soc2", "status": "current", "issued_on": "2026-03-01", "expires_on": "2027-03-01"},
            {"vendor_id": "payflow", "evidence_type": "pentest", "status": "current", "issued_on": "2026-02-01", "expires_on": "2027-02-01"},
            {"vendor_id": "chatly", "evidence_type": "soc2", "status": "current", "issued_on": "2025-02-01", "expires_on": "2026-02-01"},
            {"vendor_id": "marketbee", "evidence_type": "soc2", "status": "current", "issued_on": "2025-09-01", "expires_on": "2026-09-01"},
            {"vendor_id": "loglake", "evidence_type": "soc2", "status": "current", "issued_on": "2026-06-01", "expires_on": "2027-06-01"},
            {"vendor_id": "docsbox", "evidence_type": "soc2", "status": "current", "issued_on": "2026-04-01", "expires_on": "2027-04-01"},
        ],
        ["vendor_id", "evidence_type", "status", "issued_on", "expires_on"],
    )
    write_csv(
        root,
        "subprocessors/subprocessors.csv",
        [
            {"vendor_id": "authzero", "subprocessor_id": "az-logs", "region": "US", "approved": "true", "data_classification": "pii"},
            {"vendor_id": "authzero", "subprocessor_id": "az-ml", "region": "CN", "approved": "false", "data_classification": "pii"},
            {"vendor_id": "payflow", "subprocessor_id": "pf-risk", "region": "US", "approved": "true", "data_classification": "financial"},
            {"vendor_id": "chatly", "subprocessor_id": "chat-transcribe", "region": "EU", "approved": "true", "data_classification": "sensitive"},
            {"vendor_id": "chatly", "subprocessor_id": "chat-translate", "region": "RU", "approved": "true", "data_classification": "sensitive"},
            {"vendor_id": "marketbee", "subprocessor_id": "mb-ads", "region": "US", "approved": "true", "data_classification": "pii"},
            {"vendor_id": "loglake", "subprocessor_id": "ll-warehouse", "region": "EU", "approved": "true", "data_classification": "pseudonymous"},
        ],
        ["vendor_id", "subprocessor_id", "region", "approved", "data_classification"],
    )
    write_csv(
        root,
        "incidents/vendor_incidents.csv",
        [
            {"vendor_id": "authzero", "severity": "P1", "status": "open", "opened_at": "2026-07-06"},
            {"vendor_id": "chatly", "severity": "P2", "status": "resolved", "opened_at": "2026-06-15"},
            {"vendor_id": "loglake", "severity": "P2", "status": "open", "opened_at": "2026-07-01"},
            {"vendor_id": "payflow", "severity": "P0", "status": "resolved", "opened_at": "2026-05-01"},
        ],
        ["vendor_id", "severity", "status", "opened_at"],
    )
    write_csv(
        root,
        "exceptions/risk_exceptions.csv",
        [
            {"vendor_id": "loglake", "control": "open_incident", "expires_on": "2026-08-01", "reason": "known logging spill"},
            {"vendor_id": "chatly", "control": "regional_review", "expires_on": "2026-06-30", "reason": "legacy translator"},
            {"vendor_id": "marketbee", "control": "renewal_review", "expires_on": "2026-06-01", "reason": "old renewal exception"},
        ],
        ["vendor_id", "control", "expires_on", "reason"],
    )

    integration_source(root, "authzero", "auth.py", "# vendor: authzero\ndef sync_authzero():\n    return 'authzero'\n")
    integration_source(root, "payflow", "payments.py", "# vendor: payflow\ndef sync_payflow():\n    return 'payflow'\n")
    integration_source(root, "chatly", "support_chat.py", "# integration uses support chat vendor\ndef sync_chat():\n    return 'chat'\n")
    integration_source(root, "marketbee", "leads.py", "# vendor: marketbee\ndef sync_marketbee():\n    return 'marketbee'\n")
    integration_source(root, "loglake", "logs.py", "# vendor: loglake\ndef sync_loglake():\n    return 'loglake'\n")
    integration_source(root, "docsbox", "docs.py", "# vendor: docsbox\ndef sync_docsbox():\n    return 'docsbox'\n")


if __name__ == "__main__":
    main()

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


def service_file(root: Path, service_id: str, body: str) -> None:
    write(root, f"repos/{service_id}/src/payment_flow.py", body)
    for index in range(1, 21):
        write(
            root,
            f"repos/{service_id}/src/generated/module_{index:02d}.py",
            f"""
            from __future__ import annotations


            SERVICE = {service_id!r}
            MODULE_INDEX = {index}


            def compute_marker(seed: int) -> str:
                return f"{{SERVICE}}:{{MODULE_INDEX}}:{{seed % 17}}"
            """,
        )


def main() -> None:
    root = Path(sys.argv[1])
    root.mkdir(parents=True, exist_ok=True)

    write(
        root,
        "README.md",
        """
        # Platform Services

        Synthetic monorepo for a payments SDK v4 migration readiness review.
        """,
    )
    write_json(
        root,
        "catalog/services.json",
        [
            {"service_id": "billing-api", "name": "Billing API", "team": "revops", "tier": 1, "runtime": "python"},
            {"service_id": "checkout", "name": "Checkout", "team": "commerce", "tier": 1, "runtime": "typescript"},
            {"service_id": "subscriptions", "name": "Subscriptions", "team": "revops", "tier": 2, "runtime": "python"},
            {"service_id": "portal", "name": "Customer Portal", "team": "growth", "tier": 3, "runtime": "python"},
            {"service_id": "ledger", "name": "Ledger", "team": "finance", "tier": 1, "runtime": "python"},
        ],
    )
    write_csv(
        root,
        "owners/teams.csv",
        [
            {"team": "commerce", "manager": "Ava Lee", "slack": "#commerce", "email": "commerce@example.com"},
            {"team": "finance", "manager": "Bo Kim", "slack": "#finance", "email": "finance@example.com"},
            {"team": "growth", "manager": "Cy Rao", "slack": "#growth", "email": "growth@example.com"},
            {"team": "revops", "manager": "Diya Shah", "slack": "#revops", "email": "revops@example.com"},
        ],
        ["team", "manager", "slack", "email"],
    )
    write_csv(
        root,
        "dependencies/packages.csv",
        [
            {"service_id": "billing-api", "package": "payments-sdk", "current_version": "3.4.8", "target_version": "4.2.0", "scope": "direct", "critical": "true"},
            {"service_id": "checkout", "package": "payments-sdk", "current_version": "3.9.0", "target_version": "4.2.0", "scope": "direct", "critical": "true"},
            {"service_id": "subscriptions", "package": "payments-sdk", "current_version": "3.7.5", "target_version": "4.2.0", "scope": "direct", "critical": "true"},
            {"service_id": "portal", "package": "payments-sdk", "current_version": "4.2.0", "target_version": "4.2.0", "scope": "direct", "critical": "false"},
            {"service_id": "ledger", "package": "payments-sdk", "current_version": "4.0.0", "target_version": "4.2.0", "scope": "direct", "critical": "true"},
        ],
        ["service_id", "package", "current_version", "target_version", "scope", "critical"],
    )
    configs = {
        "billing-api": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "ring", "allow_legacy_webhooks": False},
        "checkout": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "ring", "allow_legacy_webhooks": False},
        "subscriptions": {"feature_flags": [], "deployment_strategy": "manual", "allow_legacy_webhooks": True},
        "portal": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "ring", "allow_legacy_webhooks": False},
        "ledger": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "manual", "allow_legacy_webhooks": False},
    }
    for service_id, config in configs.items():
        write_json(root, f"configs/{service_id}.json", config)

    ci_logs = {
        "billing-api": "STATUS=pass\nWARN legacy call remains in billing adapter\n",
        "checkout": "STATUS=fail\nLEGACY_CONTRACT_TEST_FAILED checkout-card-contract\n",
        "subscriptions": "STATUS=pass\nWARN webhook compatibility path active\n",
        "portal": "STATUS=pass\n",
        "ledger": "STATUS=pass\n",
    }
    for service_id, log in ci_logs.items():
        write(root, f"ci/{service_id}.log", log)

    write_csv(
        root,
        "incidents/incidents.csv",
        [
            {"service_id": "checkout", "date": "2026-07-06", "severity": "P1", "status": "open"},
            {"service_id": "billing-api", "date": "2026-06-30", "severity": "P2", "status": "open"},
            {"service_id": "ledger", "date": "2026-07-01", "severity": "P1", "status": "resolved"},
        ],
        ["service_id", "date", "severity", "status"],
    )
    write_csv(
        root,
        "migration/exceptions.csv",
        [
            {"service_id": "subscriptions", "expires_on": "2026-07-20", "reason": "webhook partner lag", "approver": "vp-platform"},
            {"service_id": "billing-api", "expires_on": "2026-06-15", "reason": "old finance export", "approver": "vp-finance"},
        ],
        ["service_id", "expires_on", "reason", "approver"],
    )
    write_json(
        root,
        "migration/waves.json",
        {
            "report_date": "2026-07-07",
            "waves": [
                {"service_id": "billing-api", "wave": "wave-1", "freeze_start": "2026-07-01", "freeze_end": "2026-07-04", "cutover_deadline": "2026-07-15"},
                {"service_id": "checkout", "wave": "wave-1", "freeze_start": "2026-07-01", "freeze_end": "2026-07-04", "cutover_deadline": "2026-07-15"},
                {"service_id": "subscriptions", "wave": "wave-2", "freeze_start": "2026-07-10", "freeze_end": "2026-07-12", "cutover_deadline": "2026-07-25"},
                {"service_id": "portal", "wave": "wave-2", "freeze_start": "2026-07-10", "freeze_end": "2026-07-12", "cutover_deadline": "2026-07-25"},
                {"service_id": "ledger", "wave": "wave-3", "freeze_start": "2026-07-07", "freeze_end": "2026-07-09", "cutover_deadline": "2026-08-05"},
            ],
        },
    )
    write(
        root,
        "advisories/payments-sdk.md",
        """
        ---
        package: payments-sdk
        affected_below: 3.6.0
        severity: critical
        action: upgrade payments-sdk to >=3.6.0 before migration
        ---

        Older SDK clients have a settlement rounding bug.
        """,
    )

    service_file(
        root,
        "billing-api",
        """
        from payments import LegacyPaymentClient


        def settle(invoice):
            return LegacyPaymentClient().legacy_charge(invoice)
        """,
    )
    service_file(
        root,
        "checkout",
        """
        from payments import PaymentClient


        def authorize(cart):
            return PaymentClient().authorize(cart)
        """,
    )
    service_file(
        root,
        "subscriptions",
        """
        from payments.webhooks import verify_webhook_legacy


        def handle(payload):
            return verify_webhook_legacy(payload)
        """,
    )
    service_file(
        root,
        "portal",
        """
        from payments import PaymentClient


        def preview(user):
            return PaymentClient().preview(user)
        """,
    )
    service_file(
        root,
        "ledger",
        """
        from ledger import LedgerClient


        def post(entry):
            return LedgerClient().post(entry)
        """,
    )


if __name__ == "__main__":
    main()

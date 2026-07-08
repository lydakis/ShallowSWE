#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import json
import subprocess
import sys
import tempfile
import unittest


VENDOR_KEYS = {
    "vendor_id",
    "owner_team",
    "criticality",
    "data_classification",
    "renewal_date",
    "risk_status",
    "missing_controls",
    "exempted_controls",
    "contract_id",
    "services",
    "source_evidence_files",
    "current_evidence",
    "stale_or_missing_evidence",
    "subprocessor_gaps",
    "regional_gaps",
    "open_incidents",
    "active_exceptions",
}
OWNER_FIELDS = [
    "owner_team",
    "vendors",
    "blocked",
    "needs_work",
    "accepted_risk",
    "ready",
    "missing_controls",
    "subprocessor_gaps",
    "regional_gaps",
    "open_incidents",
    "renewals_due",
]
PLAN_FIELDS = ["vendor_id", "owner_team", "priority", "due_date", "actions", "evidence"]
SUMMARY_KEYS = {
    "vendors",
    "owners",
    "blocked",
    "needs_work",
    "accepted_risk",
    "ready",
    "missing_controls",
    "subprocessor_gaps",
    "regional_gaps",
    "open_incidents",
    "renewals_due",
    "active_exceptions",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_audit(root: Path, output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/build_vendor_risk.py"),
            "--root",
            str(root),
            "--output",
            str(output),
        ],
        check=True,
    )


def copy_script_to_hidden(root: Path) -> None:
    script = Path("/app/scripts/build_vendor_risk.py")
    target = root / "scripts/build_vendor_risk.py"
    target.parent.mkdir(parents=True)
    target.write_text(script.read_text())


def write_hidden_fixture(root: Path) -> None:
    copy_script_to_hidden(root)
    write_json(
        root / "policies/vendor_risk_policy.json",
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
            "due_days": {"blocked": 3, "needs_work": 14, "accepted_risk": 30, "ready": 60},
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
        root / "inventory/vendors.csv",
        [
            {"vendor_id": "alphaid", "owner_team": "platform", "criticality": "critical", "data_classification": "pii", "renewal_date": "2026-09-01", "status": "active", "contract_id": "c-alphaid"},
            {"vendor_id": "carebot", "owner_team": "care", "criticality": "high", "data_classification": "sensitive", "renewal_date": "2026-07-18", "status": "active", "contract_id": "c-carebot"},
            {"vendor_id": "metricsco", "owner_team": "data", "criticality": "medium", "data_classification": "pseudonymous", "renewal_date": "2026-11-01", "status": "active", "contract_id": "c-metricsco"},
            {"vendor_id": "vaultpay", "owner_team": "finance", "criticality": "critical", "data_classification": "financial", "renewal_date": "2026-07-30", "status": "active", "contract_id": "c-vaultpay"},
        ],
        ["vendor_id", "owner_team", "criticality", "data_classification", "renewal_date", "status", "contract_id"],
    )
    write_json(
        root / "inventory/services.json",
        [
            {"service_id": "alpha-sso", "vendor_id": "alphaid", "owner_team": "platform", "production": True, "data_types": ["pii"]},
            {"service_id": "care-reply", "vendor_id": "carebot", "owner_team": "care", "production": True, "data_types": ["sensitive"]},
            {"service_id": "metrics-warehouse", "vendor_id": "metricsco", "owner_team": "data", "production": True, "data_types": ["pseudonymous"]},
            {"service_id": "vault-payments", "vendor_id": "vaultpay", "owner_team": "finance", "production": True, "data_types": ["financial"]},
        ],
    )
    write_csv(
        root / "contracts/contracts.csv",
        [
            {"contract_id": "c-alphaid", "vendor_id": "alphaid", "dpa_signed": "true", "subprocessor_notice_days": 30, "termination_days": 30},
            {"contract_id": "c-carebot", "vendor_id": "carebot", "dpa_signed": "false", "subprocessor_notice_days": 7, "termination_days": 30},
            {"contract_id": "c-metricsco", "vendor_id": "metricsco", "dpa_signed": "true", "subprocessor_notice_days": 14, "termination_days": 30},
            {"contract_id": "c-vaultpay", "vendor_id": "vaultpay", "dpa_signed": "true", "subprocessor_notice_days": 30, "termination_days": 60},
        ],
        ["contract_id", "vendor_id", "dpa_signed", "subprocessor_notice_days", "termination_days"],
    )
    write_csv(
        root / "security/evidence.csv",
        [
            {"vendor_id": "alphaid", "evidence_type": "soc2", "status": "current", "issued_on": "2025-01-01", "expires_on": "2026-01-01"},
            {"vendor_id": "alphaid", "evidence_type": "pentest", "status": "current", "issued_on": "2026-04-01", "expires_on": "2027-04-01"},
            {"vendor_id": "carebot", "evidence_type": "soc2", "status": "current", "issued_on": "2026-03-01", "expires_on": "2027-03-01"},
            {"vendor_id": "vaultpay", "evidence_type": "soc2", "status": "current", "issued_on": "2026-02-01", "expires_on": "2027-02-01"},
            {"vendor_id": "vaultpay", "evidence_type": "pentest", "status": "current", "issued_on": "2026-02-15", "expires_on": "2027-02-15"},
        ],
        ["vendor_id", "evidence_type", "status", "issued_on", "expires_on"],
    )
    write_csv(
        root / "subprocessors/subprocessors.csv",
        [
            {"vendor_id": "alphaid", "subprocessor_id": "alpha-cache", "region": "US", "approved": "false", "data_classification": "pii"},
            {"vendor_id": "carebot", "subprocessor_id": "care-translate", "region": "CN", "approved": "true", "data_classification": "sensitive"},
            {"vendor_id": "metricsco", "subprocessor_id": "metrics-store", "region": "EU", "approved": "true", "data_classification": "pseudonymous"},
            {"vendor_id": "vaultpay", "subprocessor_id": "vault-risk", "region": "US", "approved": "true", "data_classification": "financial"},
        ],
        ["vendor_id", "subprocessor_id", "region", "approved", "data_classification"],
    )
    write_csv(
        root / "incidents/vendor_incidents.csv",
        [
            {"vendor_id": "metricsco", "severity": "P2", "status": "open", "opened_at": "2026-07-05"}
        ],
        ["vendor_id", "severity", "status", "opened_at"],
    )
    write_csv(
        root / "exceptions/risk_exceptions.csv",
        [
            {"vendor_id": "metricsco", "control": "open_incident", "expires_on": "2026-08-01", "reason": "contained logging issue"}
        ],
        ["vendor_id", "control", "expires_on", "reason"],
    )
    write(root / "integrations/alphaid/src/sso.py", "# vendor: alphaid\n")
    write(root / "integrations/carebot/src/reply.py", "# support assistant integration\n")
    write(root / "integrations/metricsco/src/events.py", "# vendor: metricsco\n")
    write(root / "integrations/vaultpay/src/payments.py", "# vendor: vaultpay\n")


class VendorRiskEvidenceTests(unittest.TestCase):
    def test_visible_fixture_outputs_expected_package_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            run_audit(Path("/app"), output)
            first = {path.name: path.read_text() for path in sorted(output.iterdir())}
            run_audit(Path("/app"), output)
            second = {path.name: path.read_text() for path in sorted(output.iterdir())}
            self.assertEqual(first, second)
            data = json.loads((output / "vendor_risk.json").read_text())
            summary = json.loads((output / "summary.json").read_text())
            owners = read_csv(output / "owner_gaps.csv")
            plan = read_csv(output / "renewal_actions.csv")

        self.assertEqual(set(data), {"vendors"})
        self.assertEqual(len(data["vendors"]), 6)
        by_id = {row["vendor_id"]: row for row in data["vendors"]}
        self.assertEqual(by_id["authzero"]["risk_status"], "blocked")
        self.assertEqual(
            by_id["authzero"]["missing_controls"],
            ["dpa", "pentest_current", "subprocessor_approval", "regional_review", "open_incident", "renewal_review"],
        )
        self.assertEqual(by_id["chatly"]["risk_status"], "needs_work")
        self.assertEqual(
            by_id["chatly"]["missing_controls"],
            ["soc2_current", "regional_review", "production_source_reference", "renewal_review"],
        )
        self.assertEqual(by_id["loglake"]["risk_status"], "accepted_risk")
        self.assertEqual(by_id["loglake"]["exempted_controls"], ["open_incident"])
        self.assertEqual(by_id["payflow"]["risk_status"], "ready")
        self.assertEqual(
            summary,
            {
                "vendors": 6,
                "owners": 6,
                "blocked": 1,
                "needs_work": 1,
                "accepted_risk": 1,
                "ready": 3,
                "missing_controls": 10,
                "subprocessor_gaps": 1,
                "regional_gaps": 2,
                "open_incidents": 2,
                "renewals_due": 2,
                "active_exceptions": 1,
            },
        )
        self.assertEqual(list(owners[0]), OWNER_FIELDS)
        self.assertEqual(list(plan[0]), PLAN_FIELDS)
        self.assertEqual([row["vendor_id"] for row in plan], ["authzero", "chatly", "loglake"])
        self.assertIn("review active risk exception", next(row["actions"] for row in plan if row["vendor_id"] == "loglake"))
        self.assertIn("subprocessor:az-ml", next(row["evidence"] for row in plan if row["vendor_id"] == "authzero"))

    def test_hidden_fixture_exercises_different_names_and_control_mix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            output = Path(tmp) / "output"
            write_hidden_fixture(root)
            run_audit(root, output)
            data = json.loads((output / "vendor_risk.json").read_text())
            summary = json.loads((output / "summary.json").read_text())
            owners = read_csv(output / "owner_gaps.csv")
            plan = read_csv(output / "renewal_actions.csv")

        self.assertTrue(all(set(row) == VENDOR_KEYS for row in data["vendors"]))
        by_id = {row["vendor_id"]: row for row in data["vendors"]}
        self.assertEqual(by_id["alphaid"]["missing_controls"], ["soc2_current", "subprocessor_approval"])
        self.assertEqual(by_id["carebot"]["missing_controls"], ["dpa", "regional_review", "production_source_reference", "renewal_review"])
        self.assertEqual(by_id["metricsco"]["risk_status"], "accepted_risk")
        self.assertEqual(by_id["vaultpay"]["risk_status"], "needs_work")
        self.assertEqual(by_id["vaultpay"]["missing_controls"], ["renewal_review"])
        self.assertEqual(
            summary,
            {
                "vendors": 4,
                "owners": 4,
                "blocked": 2,
                "needs_work": 1,
                "accepted_risk": 1,
                "ready": 0,
                "missing_controls": 7,
                "subprocessor_gaps": 1,
                "regional_gaps": 1,
                "open_incidents": 1,
                "renewals_due": 2,
                "active_exceptions": 1,
            },
        )
        self.assertEqual(next(row for row in owners if row["owner_team"] == "care")["missing_controls"], "4")
        self.assertEqual([row["vendor_id"] for row in plan], ["carebot", "alphaid", "vaultpay", "metricsco"])
        self.assertEqual(next(row for row in plan if row["vendor_id"] == "metricsco")["priority"], "P3")

    def test_output_schemas_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            run_audit(Path("/app"), output)
            data = json.loads((output / "vendor_risk.json").read_text())
            owners = read_csv(output / "owner_gaps.csv")
            plan = read_csv(output / "renewal_actions.csv")
            summary = json.loads((output / "summary.json").read_text())
            files = sorted(path.name for path in output.iterdir())

        self.assertEqual(files, ["owner_gaps.csv", "renewal_actions.csv", "summary.json", "vendor_risk.json"])
        self.assertTrue(all(set(row) == VENDOR_KEYS for row in data["vendors"]))
        self.assertEqual(list(owners[0]), OWNER_FIELDS)
        self.assertEqual(list(plan[0]), PLAN_FIELDS)
        self.assertEqual(set(summary), SUMMARY_KEYS)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VendorRiskEvidenceTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"

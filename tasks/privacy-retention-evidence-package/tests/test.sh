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


DATASET_KEYS = {
    "dataset_id",
    "system_id",
    "owner_team",
    "classification",
    "subject_type",
    "expected_retention_days",
    "configured_retention_days",
    "deletion_mode",
    "status",
    "missing_controls",
    "exempted_controls",
    "legal_hold_active",
    "downstream_delete_gaps",
    "downstream_export_gaps",
    "source_evidence_files",
    "purge_jobs",
    "export_jobs",
    "open_incidents",
}
OWNER_FIELDS = [
    "owner_team",
    "datasets",
    "blocked",
    "needs_work",
    "accepted_risk",
    "ready",
    "missing_controls",
    "downstream_gaps",
    "open_incidents",
    "legal_holds",
]
PLAN_FIELDS = ["dataset_id", "owner_team", "priority", "due_date", "actions", "evidence"]
SUMMARY_KEYS = {
    "datasets",
    "owners",
    "blocked",
    "needs_work",
    "accepted_risk",
    "ready",
    "missing_controls",
    "downstream_delete_gaps",
    "downstream_export_gaps",
    "open_incidents",
    "legal_holds",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run_audit(root: Path, output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/build_retention_audit.py"),
            "--root",
            str(root),
            "--output",
            str(output),
        ],
        check=True,
    )


def copy_script_to_hidden(root: Path) -> None:
    script = Path("/app/scripts/build_retention_audit.py")
    target = root / "scripts/build_retention_audit.py"
    target.parent.mkdir(parents=True)
    target.write_text(script.read_text())


def write_hidden_fixture(root: Path) -> None:
    copy_script_to_hidden(root)
    write_json(
        root / "catalog/systems.json",
        [
            {"system_id": "accounts", "owner_team": "platform", "tier": 1},
            {"system_id": "support", "owner_team": "care", "tier": 2},
            {"system_id": "research", "owner_team": "research", "tier": 2},
            {"system_id": "docs", "owner_team": "docs", "tier": 3},
            {"system_id": "billing", "owner_team": "finance", "tier": 1},
        ],
    )
    write_csv(
        root / "catalog/datasets.csv",
        [
            {"dataset_id": "accounts.profiles", "system_id": "accounts", "owner_team": "platform", "classification": "pii", "subject_type": "customer", "retention_days": 400, "deletion_mode": "hard_delete", "storage_path": "s3://accounts/profiles"},
            {"dataset_id": "support.notes", "system_id": "support", "owner_team": "care", "classification": "sensitive", "subject_type": "customer", "retention_days": 500, "deletion_mode": "hard_delete", "storage_path": "postgres://support/notes"},
            {"dataset_id": "research.events", "system_id": "research", "owner_team": "research", "classification": "pseudonymous", "subject_type": "customer", "retention_days": 220, "deletion_mode": "partition_drop", "storage_path": "warehouse.research.events"},
            {"dataset_id": "docs.public", "system_id": "docs", "owner_team": "docs", "classification": "public", "subject_type": "none", "retention_days": 3650, "deletion_mode": "none", "storage_path": "s3://docs/public"},
            {"dataset_id": "billing.records", "system_id": "billing", "owner_team": "finance", "classification": "financial", "subject_type": "customer", "retention_days": 2555, "deletion_mode": "archive", "storage_path": "s3://billing/records"},
        ],
        ["dataset_id", "system_id", "owner_team", "classification", "subject_type", "retention_days", "deletion_mode", "storage_path"],
    )
    write_json(
        root / "policies/retention_policy.json",
        {
            "report_date": "2026-07-07",
            "classification_retention_days": {"pii": 365, "sensitive": 540, "financial": 2555, "pseudonymous": 180, "public": 3650},
            "stale_job_days": 14,
            "export_job_stale_days": 30,
            "propagation_required_classifications": ["pii", "sensitive", "pseudonymous"],
            "due_days": {"blocked": 1, "needs_work": 7, "accepted_risk": 14, "ready": 30},
            "action_order": ["retention_limit", "purge_job", "purge_job_current", "subject_export", "downstream_delete", "downstream_export", "source_reference", "open_incident", "legal_hold"],
        },
    )
    write_csv(
        root / "jobs/purge_jobs.csv",
        [
            {"job_id": "purge-accounts", "dataset_id": "accounts.profiles", "mode": "hard_delete", "schedule_days": 30, "last_success_at": "2026-07-01", "filter_expr": "created_at < cutoff"},
            {"job_id": "drop-research", "dataset_id": "research.events", "mode": "partition_drop", "schedule_days": 7, "last_success_at": "2026-07-04", "filter_expr": "event_date < cutoff"},
            {"job_id": "archive-billing", "dataset_id": "billing.records", "mode": "archive", "schedule_days": 30, "last_success_at": "2026-07-02", "filter_expr": "invoice_date < cutoff"},
        ],
        ["job_id", "dataset_id", "mode", "schedule_days", "last_success_at", "filter_expr"],
    )
    write_csv(
        root / "jobs/export_jobs.csv",
        [
            {"job_id": "export-accounts", "dataset_id": "accounts.profiles", "last_success_at": "2026-07-04", "scope": "subject"},
            {"job_id": "export-support", "dataset_id": "support.notes", "last_success_at": "2026-05-15", "scope": "subject"},
            {"job_id": "export-research-agg", "dataset_id": "research.events", "last_success_at": "2026-07-03", "scope": "aggregate"},
            {"job_id": "export-billing", "dataset_id": "billing.records", "last_success_at": "2026-07-01", "scope": "subject"},
        ],
        ["job_id", "dataset_id", "last_success_at", "scope"],
    )
    write_csv(
        root / "legal/holds.csv",
        [
            {"hold_id": "hold-billing", "dataset_id": "billing.records", "status": "active", "expires_on": "2026-09-01", "reason": "tax audit"}
        ],
        ["hold_id", "dataset_id", "status", "expires_on", "reason"],
    )
    write_csv(
        root / "lineage/downstream_edges.csv",
        [
            {"source_dataset_id": "accounts.profiles", "target_dataset_id": "research.events", "delete_propagates": "false", "export_propagates": "true"},
            {"source_dataset_id": "support.notes", "target_dataset_id": "research.events", "delete_propagates": "true", "export_propagates": "false"},
        ],
        ["source_dataset_id", "target_dataset_id", "delete_propagates", "export_propagates"],
    )
    write_csv(
        root / "incidents/data_incidents.csv",
        [
            {"dataset_id": "accounts.profiles", "severity": "P1", "status": "open", "opened_at": "2026-07-06"}
        ],
        ["dataset_id", "severity", "status", "opened_at"],
    )
    write_csv(
        root / "exemptions/retention_exemptions.csv",
        [
            {"dataset_id": "research.events", "control": "retention_limit", "expires_on": "2026-08-01", "reason": "warehouse migration"}
        ],
        ["dataset_id", "control", "expires_on", "reason"],
    )
    write(root / "services/accounts/src/profiles.py", "# dataset: accounts.profiles\n")
    write(root / "services/support/src/notes.py", "# dataset: support.notes\n")
    write(root / "services/research/src/events.py", "# dataset: research.events\n")
    write(root / "services/docs/src/public.py", "# dataset: docs.public\n")
    write(root / "services/billing/src/records.py", "# dataset: billing.records\n")


class PrivacyRetentionEvidenceTests(unittest.TestCase):
    def test_visible_fixture_outputs_expected_package_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            run_audit(Path("/app"), output)
            first = {path.name: path.read_text() for path in sorted(output.iterdir())}
            run_audit(Path("/app"), output)
            second = {path.name: path.read_text() for path in sorted(output.iterdir())}
            self.assertEqual(first, second)
            data = json.loads((output / "dataset_retention.json").read_text())
            summary = json.loads((output / "summary.json").read_text())
            owners = read_csv(output / "owner_gaps.csv")
            plan = read_csv(output / "purge_plan.csv")

        self.assertEqual(set(data), {"datasets"})
        self.assertEqual(len(data["datasets"]), 7)
        self.assertEqual({row["dataset_id"] for row in data["datasets"]}, {
            "identity.users",
            "identity.sessions",
            "support.tickets",
            "billing.invoices",
            "analytics.events",
            "marketing.leads",
            "support.macros",
        })
        by_id = {row["dataset_id"]: row for row in data["datasets"]}
        self.assertEqual(by_id["identity.users"]["status"], "blocked")
        self.assertEqual(by_id["identity.users"]["missing_controls"], ["retention_limit", "purge_job_current", "downstream_delete"])
        self.assertEqual(by_id["billing.invoices"]["status"], "accepted_risk")
        self.assertEqual(by_id["analytics.events"]["exempted_controls"], ["retention_limit"])
        self.assertEqual(by_id["marketing.leads"]["missing_controls"], ["purge_job", "subject_export"])
        self.assertEqual(
            summary,
            {
                "datasets": 7,
                "owners": 5,
                "blocked": 4,
                "needs_work": 2,
                "accepted_risk": 1,
                "ready": 0,
                "missing_controls": 15,
                "downstream_delete_gaps": 2,
                "downstream_export_gaps": 2,
                "open_incidents": 2,
                "legal_holds": 2,
            },
        )
        self.assertEqual(list(owners[0]), OWNER_FIELDS)
        self.assertEqual(list(plan[0]), PLAN_FIELDS)
        self.assertEqual([row["priority"] for row in plan[:4]], ["P0", "P0", "P0", "P0"])
        self.assertIn("review active legal hold", next(row["actions"] for row in plan if row["dataset_id"] == "billing.invoices"))

    def test_hidden_fixture_exercises_different_names_and_control_mix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            output = Path(tmp) / "output"
            write_hidden_fixture(root)
            run_audit(root, output)
            data = json.loads((output / "dataset_retention.json").read_text())
            summary = json.loads((output / "summary.json").read_text())
            owners = read_csv(output / "owner_gaps.csv")
            plan = read_csv(output / "purge_plan.csv")

        self.assertTrue(all(set(row) == DATASET_KEYS for row in data["datasets"]))
        by_id = {row["dataset_id"]: row for row in data["datasets"]}
        self.assertEqual(by_id["accounts.profiles"]["status"], "blocked")
        self.assertEqual(by_id["accounts.profiles"]["missing_controls"], ["retention_limit", "downstream_delete", "open_incident"])
        self.assertEqual(by_id["support.notes"]["missing_controls"], ["purge_job", "subject_export", "downstream_export"])
        self.assertEqual(by_id["research.events"]["status"], "needs_work")
        self.assertEqual(by_id["research.events"]["exempted_controls"], ["retention_limit"])
        self.assertEqual(by_id["billing.records"]["status"], "accepted_risk")
        self.assertEqual(by_id["docs.public"]["status"], "ready")
        self.assertEqual(
            summary,
            {
                "datasets": 5,
                "owners": 5,
                "blocked": 2,
                "needs_work": 1,
                "accepted_risk": 1,
                "ready": 1,
                "missing_controls": 7,
                "downstream_delete_gaps": 1,
                "downstream_export_gaps": 1,
                "open_incidents": 1,
                "legal_holds": 1,
            },
        )
        self.assertEqual(next(row for row in owners if row["owner_team"] == "platform")["missing_controls"], "3")
        self.assertEqual([row["dataset_id"] for row in plan], ["accounts.profiles", "support.notes", "research.events", "billing.records"])
        self.assertEqual(next(row for row in plan if row["dataset_id"] == "billing.records")["priority"], "P3")

    def test_output_schemas_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            run_audit(Path("/app"), output)
            data = json.loads((output / "dataset_retention.json").read_text())
            owners = read_csv(output / "owner_gaps.csv")
            plan = read_csv(output / "purge_plan.csv")
            summary = json.loads((output / "summary.json").read_text())
            files = sorted(path.name for path in output.iterdir())

        self.assertEqual(files, ["dataset_retention.json", "owner_gaps.csv", "purge_plan.csv", "summary.json"])
        self.assertTrue(all(set(row) == DATASET_KEYS for row in data["datasets"]))
        self.assertEqual(list(owners[0]), OWNER_FIELDS)
        self.assertEqual(list(plan[0]), PLAN_FIELDS)
        self.assertEqual(set(summary), SUMMARY_KEYS)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PrivacyRetentionEvidenceTests)
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

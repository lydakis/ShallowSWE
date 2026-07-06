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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def run_restate(input_dir: Path, output_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ledger_restate.cli",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
    )


def write_hidden_fixture(root: Path) -> Path:
    input_dir = root / "input"
    months = input_dir / "months"
    months.mkdir(parents=True)
    (months / "2026-04.csv").write_text(
        "entry_id,account_id,posted_at,amount_cents,memo\n"
        "apr-001,acct-a,2026-04-01T10:00:00Z,10000,subscription\n"
        "apr-002,acct-b,2026-04-12T11:00:00Z,3000,usage\n"
    )
    (months / "2026-05.csv").write_text(
        "entry_id,account_id,posted_at,amount_cents,memo\n"
        "may-001,acct-a,2026-05-01T10:00:00Z,12000,subscription\n"
        "may-002,acct-c,2026-05-21T15:30:00Z,-2000,credit\n"
    )
    (months / "2026-06.csv").write_text(
        "entry_id,account_id,posted_at,amount_cents,memo\n"
        "jun-001,acct-a,2026-06-01T10:00:00Z,13000,subscription\n"
    )
    (input_dir / "corrections.csv").write_text(
        "correction_id,target_entry_id,restated_amount_cents,reason,applied_at\n"
        "hc-002,apr-002,4500,late_usage,2026-07-02T09:00:00Z\n"
        "hc-001,apr-002,3500,initial_usage_fix,2026-07-01T09:00:00Z\n"
        "hc-003,may-001,10000,downgrade_backdate,2026-07-03T09:00:00Z\n"
        "hc-004,missing-999,777,unknown_entry,2026-07-04T09:00:00Z\n"
    )
    return input_dir


class LedgerRestatementAuditTests(unittest.TestCase):
    def test_visible_fixture_outputs_exact_package_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output"
            run_restate(Path("/app/input"), output)

            first = {
                "rollups": (output / "restated_rollups.csv").read_text(),
                "audit": (output / "correction_audit.csv").read_text(),
                "summary": (output / "summary.json").read_text(),
            }
            run_restate(Path("/app/input"), output)
            second = {
                "rollups": (output / "restated_rollups.csv").read_text(),
                "audit": (output / "correction_audit.csv").read_text(),
                "summary": (output / "summary.json").read_text(),
            }
            rollups = read_csv(output / "restated_rollups.csv")
            audit = read_csv(output / "correction_audit.csv")
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(first, second)
        self.assertEqual(
            rollups,
            [
                {
                    "month": "2026-01",
                    "gross_cents": "15000",
                    "correction_delta_cents": "-500",
                    "net_cents": "14500",
                    "entry_count": "2",
                },
                {
                    "month": "2026-02",
                    "gross_cents": "6000",
                    "correction_delta_cents": "2000",
                    "net_cents": "8000",
                    "entry_count": "2",
                },
            ],
        )
        self.assertEqual(
            audit,
            [
                {
                    "correction_id": "corr-001",
                    "target_entry_id": "jan-002",
                    "month": "2026-01",
                    "original_amount_cents": "5000",
                    "restated_amount_cents": "4500",
                    "delta_cents": "-500",
                    "status": "applied",
                    "reason": "usage_reprice",
                },
                {
                    "correction_id": "corr-002",
                    "target_entry_id": "feb-001",
                    "month": "2026-02",
                    "original_amount_cents": "7000",
                    "restated_amount_cents": "9000",
                    "delta_cents": "2000",
                    "status": "applied",
                    "reason": "late_upgrade",
                },
                {
                    "correction_id": "corr-003",
                    "target_entry_id": "missing-001",
                    "month": "",
                    "original_amount_cents": "",
                    "restated_amount_cents": "1200",
                    "delta_cents": "",
                    "status": "rejected_unknown_entry",
                    "reason": "unknown_entry",
                },
            ],
        )
        self.assertEqual(
            summary,
            {
                "months": 2,
                "entries": 4,
                "accepted_corrections": 2,
                "rejected_corrections": 1,
                "gross_cents": 21000,
                "correction_delta_cents": 1500,
                "net_cents": 22500,
            },
        )

    def test_hidden_fixture_handles_ordering_chained_corrections_and_unknown_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = write_hidden_fixture(root)
            output = root / "output"
            run_restate(input_dir, output)

            rollups = read_csv(output / "restated_rollups.csv")
            audit = read_csv(output / "correction_audit.csv")
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(
            rollups,
            [
                {
                    "month": "2026-04",
                    "gross_cents": "13000",
                    "correction_delta_cents": "1500",
                    "net_cents": "14500",
                    "entry_count": "2",
                },
                {
                    "month": "2026-05",
                    "gross_cents": "10000",
                    "correction_delta_cents": "-2000",
                    "net_cents": "8000",
                    "entry_count": "2",
                },
                {
                    "month": "2026-06",
                    "gross_cents": "13000",
                    "correction_delta_cents": "0",
                    "net_cents": "13000",
                    "entry_count": "1",
                },
            ],
        )
        self.assertEqual([row["correction_id"] for row in audit], ["hc-001", "hc-002", "hc-003", "hc-004"])
        self.assertEqual(audit[0]["original_amount_cents"], "3000")
        self.assertEqual(audit[0]["delta_cents"], "500")
        self.assertEqual(audit[1]["original_amount_cents"], "3500")
        self.assertEqual(audit[1]["delta_cents"], "1000")
        self.assertEqual(audit[3]["status"], "rejected_unknown_entry")
        self.assertEqual(
            summary,
            {
                "months": 3,
                "entries": 5,
                "accepted_corrections": 3,
                "rejected_corrections": 1,
                "gross_cents": 36000,
                "correction_delta_cents": -500,
                "net_cents": 35500,
            },
        )

    def test_output_schemas_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            run_restate(Path("/app/input"), output)

            rollups = read_csv(output / "restated_rollups.csv")
            audit = read_csv(output / "correction_audit.csv")
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(
            list(rollups[0]),
            ["month", "gross_cents", "correction_delta_cents", "net_cents", "entry_count"],
        )
        self.assertEqual(
            list(audit[0]),
            [
                "correction_id",
                "target_entry_id",
                "month",
                "original_amount_cents",
                "restated_amount_cents",
                "delta_cents",
                "status",
                "reason",
            ],
        )
        self.assertEqual(
            set(summary),
            {
                "months",
                "entries",
                "accepted_corrections",
                "rejected_corrections",
                "gross_cents",
                "correction_delta_cents",
                "net_cents",
            },
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LedgerRestatementAuditTests)
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

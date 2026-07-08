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


ROLLUP_FIELDS = [
    "month",
    "entity_id",
    "currency",
    "gross_cents",
    "net_cents",
    "correction_delta_cents",
    "original_entry_count",
    "final_entry_count",
]
AUDIT_FIELDS = [
    "correction_id",
    "target_entry_id",
    "status",
    "reason",
    "before_month",
    "after_month",
    "before_account_id",
    "after_account_id",
    "before_amount_cents",
    "after_amount_cents",
    "delta_cents",
    "approval_id",
]
OWNER_FIELDS = [
    "owner_team",
    "applied_corrections",
    "rejected_corrections",
    "net_delta_cents",
    "moved_in_entries",
    "moved_out_entries",
    "material_corrections",
]
SUMMARY_KEYS = {
    "months",
    "entities",
    "currencies",
    "entries",
    "accepted_corrections",
    "rejected_corrections",
    "locked_rejections",
    "approval_rejections",
    "gross_cents",
    "correction_delta_cents",
    "net_cents",
    "moved_entries",
    "material_corrections",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def month(posted_at: str) -> str:
    return posted_at[:7]


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def blank_audit(correction: dict[str, str], status: str) -> dict[str, object]:
    return {
        "correction_id": correction["correction_id"],
        "target_entry_id": correction["target_entry_id"],
        "status": status,
        "reason": correction["reason"],
        "before_month": "",
        "after_month": "",
        "before_account_id": "",
        "after_account_id": "",
        "before_amount_cents": "",
        "after_amount_cents": "",
        "delta_cents": "",
        "approval_id": "",
    }


def as_csv_strings(rows: list[dict[str, object]]) -> list[dict[str, str]]:
    return [{key: str(value) for key, value in row.items()} for row in rows]


def expected_package(input_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    accounts = {row["account_id"]: row for row in read_csv(input_dir / "accounts.csv")}
    for account in accounts.values():
        account["materiality_cents"] = int(account["materiality_cents"])  # type: ignore[index]
    periods = {row["month"]: row["status"] for row in read_csv(input_dir / "periods.csv")}
    approvals_by_correction: dict[str, list[dict[str, str]]] = {}
    approval_path = input_dir / "correction_approvals.csv"
    if approval_path.exists():
        for approval in read_csv(approval_path):
            approvals_by_correction.setdefault(approval["correction_id"], []).append(approval)

    entries: dict[str, dict[str, object]] = {}
    for path in sorted((input_dir / "months").glob("*.csv")):
        for row in read_csv(path):
            amount = int(row["amount_cents"])
            entries[row["entry_id"]] = {
                "entry_id": row["entry_id"],
                "original_account_id": row["account_id"],
                "original_posted_at": row["posted_at"],
                "original_amount_cents": amount,
                "current_account_id": row["account_id"],
                "current_posted_at": row["posted_at"],
                "current_amount_cents": amount,
            }

    owner_stats: dict[str, dict[str, int]] = {}

    def stats(owner: str) -> dict[str, int]:
        return owner_stats.setdefault(
            owner,
            {
                "applied_corrections": 0,
                "rejected_corrections": 0,
                "net_delta_cents": 0,
                "moved_in_entries": 0,
                "moved_out_entries": 0,
                "material_corrections": 0,
            },
        )

    audit_rows: list[dict[str, object]] = []
    accepted = rejected = locked_rejections = approval_rejections = 0
    moved_entries = material_corrections = 0

    corrections = sorted(
        read_csv(input_dir / "corrections.csv"),
        key=lambda row: (row["applied_at"], row["correction_id"]),
    )
    for correction in corrections:
        entry = entries.get(correction["target_entry_id"])
        if entry is None:
            rejected += 1
            stats("unassigned")["rejected_corrections"] += 1
            audit_rows.append(blank_audit(correction, "rejected_unknown_entry"))
            continue

        before_account_id = str(entry["current_account_id"])
        before_account = accounts[before_account_id]
        before_month = month(str(entry["current_posted_at"]))
        before_amount = int(entry["current_amount_cents"])
        after_amount = int(correction["restated_amount_cents"]) if correction["restated_amount_cents"].strip() else before_amount
        after_account_id = correction["new_account_id"].strip() or before_account_id
        after_posted_at = correction["new_posted_at"].strip() or str(entry["current_posted_at"])
        after_month = month(after_posted_at)
        delta = after_amount - before_amount
        approval_id = ""
        row: dict[str, object] = {
            "correction_id": correction["correction_id"],
            "target_entry_id": correction["target_entry_id"],
            "status": "",
            "reason": correction["reason"],
            "before_month": before_month,
            "after_month": after_month,
            "before_account_id": before_account_id,
            "after_account_id": after_account_id,
            "before_amount_cents": before_amount,
            "after_amount_cents": after_amount,
            "delta_cents": delta,
            "approval_id": "",
        }

        after_account = accounts.get(after_account_id)
        if after_account is None:
            status = "rejected_unknown_account"
        elif periods.get(before_month, "open") == "locked" or periods.get(after_month, "open") == "locked":
            status = "rejected_locked_period"
        else:
            approval_required = (
                truthy(correction["requires_approval"])
                or periods.get(before_month, "open") == "closed"
                or periods.get(after_month, "open") == "closed"
                or abs(delta) > int(before_account["materiality_cents"])  # type: ignore[arg-type]
            )
            if approval_required:
                for approval in approvals_by_correction.get(correction["correction_id"], []):
                    if approval["approval_id"].strip() and abs(delta) <= int(approval["limit_cents"]):
                        approval_id = approval["approval_id"]
                        break
            if approval_required and not approval_id:
                status = "rejected_missing_approval"
            elif after_amount == before_amount and after_account_id == before_account_id and after_posted_at == entry["current_posted_at"]:
                status = "rejected_noop"
            else:
                status = "applied"

        if status != "applied":
            row["status"] = status
            audit_rows.append(row)
            rejected += 1
            stats(str(before_account["owner_team"]))["rejected_corrections"] += 1
            locked_rejections += int(status == "rejected_locked_period")
            approval_rejections += int(status == "rejected_missing_approval")
            continue

        assert after_account is not None
        row["status"] = "applied"
        row["approval_id"] = approval_id
        audit_rows.append(row)
        accepted += 1
        before_stats = stats(str(before_account["owner_team"]))
        before_stats["applied_corrections"] += 1
        before_stats["net_delta_cents"] += delta
        if abs(delta) > int(before_account["materiality_cents"]):  # type: ignore[arg-type]
            before_stats["material_corrections"] += 1
            material_corrections += 1
        if before_account["owner_team"] != after_account["owner_team"]:
            before_stats["moved_out_entries"] += 1
            stats(str(after_account["owner_team"]))["moved_in_entries"] += 1
            moved_entries += 1
        entry["current_account_id"] = after_account_id
        entry["current_posted_at"] = after_posted_at
        entry["current_amount_cents"] = after_amount

    groups: dict[tuple[str, str, str], dict[str, int]] = {}
    for entry in entries.values():
        original_account = accounts[str(entry["original_account_id"])]
        original_key = (
            month(str(entry["original_posted_at"])),
            str(original_account["entity_id"]),
            str(original_account["currency"]),
        )
        groups.setdefault(original_key, {"gross_cents": 0, "net_cents": 0, "original_entry_count": 0, "final_entry_count": 0})
        groups[original_key]["gross_cents"] += int(entry["original_amount_cents"])
        groups[original_key]["original_entry_count"] += 1

        current_account = accounts[str(entry["current_account_id"])]
        current_key = (
            month(str(entry["current_posted_at"])),
            str(current_account["entity_id"]),
            str(current_account["currency"]),
        )
        groups.setdefault(current_key, {"gross_cents": 0, "net_cents": 0, "original_entry_count": 0, "final_entry_count": 0})
        groups[current_key]["net_cents"] += int(entry["current_amount_cents"])
        groups[current_key]["final_entry_count"] += 1

    rollups = []
    for key in sorted(groups):
        group = groups[key]
        rollups.append(
            {
                "month": key[0],
                "entity_id": key[1],
                "currency": key[2],
                "gross_cents": group["gross_cents"],
                "net_cents": group["net_cents"],
                "correction_delta_cents": group["net_cents"] - group["gross_cents"],
                "original_entry_count": group["original_entry_count"],
                "final_entry_count": group["final_entry_count"],
            }
        )

    owners = [{"owner_team": owner, **values} for owner, values in sorted(owner_stats.items())]
    gross_total = sum(int(entry["original_amount_cents"]) for entry in entries.values())
    net_total = sum(int(entry["current_amount_cents"]) for entry in entries.values())
    summary = {
        "months": len({row["month"] for row in rollups}),
        "entities": len({row["entity_id"] for row in rollups}),
        "currencies": len({row["currency"] for row in rollups}),
        "entries": len(entries),
        "accepted_corrections": accepted,
        "rejected_corrections": rejected,
        "locked_rejections": locked_rejections,
        "approval_rejections": approval_rejections,
        "gross_cents": gross_total,
        "correction_delta_cents": net_total - gross_total,
        "net_cents": net_total,
        "moved_entries": moved_entries,
        "material_corrections": material_corrections,
    }
    return as_csv_strings(rollups), as_csv_strings(audit_rows), as_csv_strings(owners), summary


def write_hidden_fixture(root: Path) -> Path:
    input_dir = root / "input"
    months = input_dir / "months"
    months.mkdir(parents=True)
    (months / "2026-05.csv").write_text(
        "entry_id,account_id,posted_at,amount_cents,memo\n"
        "h-001,acct-rev-na,2026-05-01T10:00:00Z,8000,subscription\n"
        "h-002,acct-contra,2026-05-09T10:00:00Z,-1000,credit\n"
    )
    (months / "2026-06.csv").write_text(
        "entry_id,account_id,posted_at,amount_cents,memo\n"
        "h-003,acct-rev-eu,2026-06-03T10:00:00Z,4000,usage\n"
    )
    write_csv(
        input_dir / "accounts.csv",
        ["account_id", "entity_id", "owner_team", "currency", "materiality_cents"],
        [
            {"account_id": "acct-rev-na", "entity_id": "ent-na", "owner_team": "ops", "currency": "USD", "materiality_cents": 1000},
            {"account_id": "acct-contra", "entity_id": "ent-na", "owner_team": "ops", "currency": "USD", "materiality_cents": 500},
            {"account_id": "acct-rev-eu", "entity_id": "ent-eu", "owner_team": "intl", "currency": "EUR", "materiality_cents": 700},
        ],
    )
    write_csv(
        input_dir / "periods.csv",
        ["month", "status"],
        [
            {"month": "2026-05", "status": "closed"},
            {"month": "2026-06", "status": "open"},
            {"month": "2026-07", "status": "locked"},
        ],
    )
    write_csv(
        input_dir / "corrections.csv",
        [
            "correction_id",
            "target_entry_id",
            "restated_amount_cents",
            "new_account_id",
            "new_posted_at",
            "reason",
            "applied_at",
            "requires_approval",
        ],
        [
            {"correction_id": "hc-001", "target_entry_id": "h-001", "restated_amount_cents": "9500", "new_account_id": "", "new_posted_at": "", "reason": "contract_backdate", "applied_at": "2026-07-01T09:00:00Z", "requires_approval": "false"},
            {"correction_id": "hc-002", "target_entry_id": "h-002", "restated_amount_cents": "", "new_account_id": "missing-acct", "new_posted_at": "", "reason": "bad_reclass", "applied_at": "2026-07-02T09:00:00Z", "requires_approval": "false"},
            {"correction_id": "hc-003", "target_entry_id": "h-003", "restated_amount_cents": "", "new_account_id": "", "new_posted_at": "2026-07-01T00:00:00Z", "reason": "locked_move", "applied_at": "2026-07-03T09:00:00Z", "requires_approval": "false"},
            {"correction_id": "hc-004", "target_entry_id": "h-003", "restated_amount_cents": "4500", "new_account_id": "", "new_posted_at": "", "reason": "usage_trueup", "applied_at": "2026-07-04T09:00:00Z", "requires_approval": "false"},
            {"correction_id": "hc-005", "target_entry_id": "h-003", "restated_amount_cents": "", "new_account_id": "acct-rev-na", "new_posted_at": "2026-05-20T00:00:00Z", "reason": "entity_move", "applied_at": "2026-07-05T09:00:00Z", "requires_approval": "true"},
            {"correction_id": "hc-006", "target_entry_id": "missing-entry", "restated_amount_cents": "1", "new_account_id": "", "new_posted_at": "", "reason": "unknown", "applied_at": "2026-07-06T09:00:00Z", "requires_approval": "false"},
            {"correction_id": "hc-007", "target_entry_id": "h-001", "restated_amount_cents": "12000", "new_account_id": "", "new_posted_at": "", "reason": "over_limit", "applied_at": "2026-07-07T09:00:00Z", "requires_approval": "false"},
        ],
    )
    write_csv(
        input_dir / "correction_approvals.csv",
        ["correction_id", "approval_id", "approved_by", "approved_at", "limit_cents"],
        [
            {"correction_id": "hc-001", "approval_id": "hap-001", "approved_by": "controller", "approved_at": "2026-06-30T20:00:00Z", "limit_cents": 2000},
            {"correction_id": "hc-005", "approval_id": "hap-005", "approved_by": "controller", "approved_at": "2026-07-04T20:00:00Z", "limit_cents": 10000},
        ],
    )
    return input_dir


class LedgerRestatementAuditTests(unittest.TestCase):
    def assert_package_matches(self, input_dir: Path, output: Path) -> None:
        expected_rollups, expected_audit, expected_owners, expected_summary = expected_package(input_dir)
        self.assertEqual(read_csv(output / "restated_rollups.csv"), expected_rollups)
        self.assertEqual(read_csv(output / "correction_audit.csv"), expected_audit)
        self.assertEqual(read_csv(output / "owner_impact.csv"), expected_owners)
        self.assertEqual(json.loads((output / "summary.json").read_text()), expected_summary)

    def test_visible_fixture_outputs_expanded_package_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output"
            run_restate(Path("/app/input"), output)
            first = {path.name: path.read_text() for path in sorted(output.iterdir())}
            run_restate(Path("/app/input"), output)
            second = {path.name: path.read_text() for path in sorted(output.iterdir())}
            self.assertEqual(first, second)
            self.assert_package_matches(Path("/app/input"), output)
            rollups = read_csv(output / "restated_rollups.csv")
            audit = read_csv(output / "correction_audit.csv")
            owners = read_csv(output / "owner_impact.csv")
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(
            rollups,
            [
                {"month": "2026-01", "entity_id": "ent-na", "currency": "USD", "gross_cents": "15000", "net_cents": "4500", "correction_delta_cents": "-10500", "original_entry_count": "2", "final_entry_count": "1"},
                {"month": "2026-02", "entity_id": "ent-eu", "currency": "EUR", "gross_cents": "-1000", "net_cents": "-1000", "correction_delta_cents": "0", "original_entry_count": "1", "final_entry_count": "1"},
                {"month": "2026-02", "entity_id": "ent-na", "currency": "USD", "gross_cents": "7000", "net_cents": "9000", "correction_delta_cents": "2000", "original_entry_count": "1", "final_entry_count": "1"},
                {"month": "2026-03", "entity_id": "ent-eu", "currency": "EUR", "gross_cents": "0", "net_cents": "10000", "correction_delta_cents": "10000", "original_entry_count": "0", "final_entry_count": "1"},
            ],
        )
        self.assertEqual(
            [row["status"] for row in audit],
            [
                "applied",
                "applied",
                "rejected_unknown_entry",
                "applied",
                "rejected_missing_approval",
                "rejected_noop",
                "rejected_locked_period",
            ],
        )
        self.assertEqual(
            owners,
            [
                {"owner_team": "finance", "applied_corrections": "3", "rejected_corrections": "2", "net_delta_cents": "1500", "moved_in_entries": "0", "moved_out_entries": "1", "material_corrections": "1"},
                {"owner_team": "success", "applied_corrections": "0", "rejected_corrections": "1", "net_delta_cents": "0", "moved_in_entries": "1", "moved_out_entries": "0", "material_corrections": "0"},
                {"owner_team": "unassigned", "applied_corrections": "0", "rejected_corrections": "1", "net_delta_cents": "0", "moved_in_entries": "0", "moved_out_entries": "0", "material_corrections": "0"},
            ],
        )
        self.assertEqual(
            summary,
            {
                "months": 3,
                "entities": 2,
                "currencies": 2,
                "entries": 4,
                "accepted_corrections": 3,
                "rejected_corrections": 4,
                "locked_rejections": 1,
                "approval_rejections": 1,
                "gross_cents": 21000,
                "correction_delta_cents": 1500,
                "net_cents": 22500,
                "moved_entries": 1,
                "material_corrections": 1,
            },
        )

    def test_hidden_fixture_covers_reclasses_approvals_locked_periods_and_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = write_hidden_fixture(root)
            output = root / "output"
            run_restate(input_dir, output)
            self.assert_package_matches(input_dir, output)
            audit = read_csv(output / "correction_audit.csv")
            summary = json.loads((output / "summary.json").read_text())

        self.assertEqual(
            [row["status"] for row in audit],
            [
                "applied",
                "rejected_unknown_account",
                "rejected_locked_period",
                "applied",
                "applied",
                "rejected_unknown_entry",
                "rejected_missing_approval",
            ],
        )
        self.assertEqual(summary["accepted_corrections"], 3)
        self.assertEqual(summary["rejected_corrections"], 4)
        self.assertEqual(summary["moved_entries"], 1)
        self.assertEqual(summary["material_corrections"], 1)

    def test_output_schemas_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            run_restate(Path("/app/input"), output)
            rollups = read_csv(output / "restated_rollups.csv")
            audit = read_csv(output / "correction_audit.csv")
            owners = read_csv(output / "owner_impact.csv")
            summary = json.loads((output / "summary.json").read_text())
            output_files = sorted(path.name for path in output.iterdir())

        self.assertEqual(list(rollups[0]), ROLLUP_FIELDS)
        self.assertEqual(list(audit[0]), AUDIT_FIELDS)
        self.assertEqual(list(owners[0]), OWNER_FIELDS)
        self.assertEqual(set(summary), SUMMARY_KEYS)
        self.assertEqual(
            output_files,
            ["correction_audit.csv", "owner_impact.csv", "restated_rollups.csv", "summary.json"],
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

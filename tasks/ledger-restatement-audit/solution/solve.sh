#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > ledger_restate/restate.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json


@dataclass
class Account:
    account_id: str
    entity_id: str
    owner_team: str
    currency: str
    materiality_cents: int


@dataclass
class Entry:
    entry_id: str
    original_account_id: str
    original_posted_at: str
    original_amount_cents: int
    current_account_id: str
    current_posted_at: str
    current_amount_cents: int


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _read_optional_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return _read_csv(path)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _month(posted_at: str) -> str:
    return posted_at[:7]


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _blank_audit_row(correction: dict[str, str], status: str) -> dict[str, object]:
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


def restate(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    accounts = {
        row["account_id"]: Account(
            account_id=row["account_id"],
            entity_id=row["entity_id"],
            owner_team=row["owner_team"],
            currency=row["currency"],
            materiality_cents=int(row["materiality_cents"]),
        )
        for row in _read_csv(input_path / "accounts.csv")
    }
    periods = {row["month"]: row["status"] for row in _read_csv(input_path / "periods.csv")}
    approvals = _read_optional_csv(input_path / "correction_approvals.csv")
    approvals_by_correction: dict[str, list[dict[str, str]]] = {}
    for approval in approvals:
        approvals_by_correction.setdefault(approval["correction_id"], []).append(approval)

    entries: dict[str, Entry] = {}
    for path in sorted((input_path / "months").glob("*.csv")):
        for row in _read_csv(path):
            amount = int(row["amount_cents"])
            entries[row["entry_id"]] = Entry(
                entry_id=row["entry_id"],
                original_account_id=row["account_id"],
                original_posted_at=row["posted_at"],
                original_amount_cents=amount,
                current_account_id=row["account_id"],
                current_posted_at=row["posted_at"],
                current_amount_cents=amount,
            )

    corrections = sorted(
        _read_csv(input_path / "corrections.csv"),
        key=lambda row: (row["applied_at"], row["correction_id"]),
    )

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
    accepted = 0
    rejected = 0
    locked_rejections = 0
    approval_rejections = 0
    moved_entries = 0
    material_corrections = 0

    for correction in corrections:
        entry = entries.get(correction["target_entry_id"])
        if entry is None:
            rejected += 1
            stats("unassigned")["rejected_corrections"] += 1
            audit_rows.append(_blank_audit_row(correction, "rejected_unknown_entry"))
            continue

        before_account = accounts[entry.current_account_id]
        before_month = _month(entry.current_posted_at)
        after_amount = (
            int(correction["restated_amount_cents"])
            if correction["restated_amount_cents"].strip()
            else entry.current_amount_cents
        )
        after_account_id = correction["new_account_id"].strip() or entry.current_account_id
        after_posted_at = correction["new_posted_at"].strip() or entry.current_posted_at
        after_month = _month(after_posted_at)
        delta = after_amount - entry.current_amount_cents
        approval_id = ""

        row = {
            "correction_id": correction["correction_id"],
            "target_entry_id": correction["target_entry_id"],
            "status": "",
            "reason": correction["reason"],
            "before_month": before_month,
            "after_month": after_month,
            "before_account_id": entry.current_account_id,
            "after_account_id": after_account_id,
            "before_amount_cents": entry.current_amount_cents,
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
                _truthy(correction["requires_approval"])
                or periods.get(before_month, "open") == "closed"
                or periods.get(after_month, "open") == "closed"
                or abs(delta) > before_account.materiality_cents
            )
            if approval_required:
                for approval in approvals_by_correction.get(correction["correction_id"], []):
                    if approval["approval_id"].strip() and abs(delta) <= int(approval["limit_cents"]):
                        approval_id = approval["approval_id"]
                        break
            if approval_required and not approval_id:
                status = "rejected_missing_approval"
            elif (
                after_amount == entry.current_amount_cents
                and after_account_id == entry.current_account_id
                and after_posted_at == entry.current_posted_at
            ):
                status = "rejected_noop"
            else:
                status = "applied"

        if status != "applied":
            row["status"] = status
            audit_rows.append(row)
            rejected += 1
            stats(before_account.owner_team)["rejected_corrections"] += 1
            if status == "rejected_locked_period":
                locked_rejections += 1
            if status == "rejected_missing_approval":
                approval_rejections += 1
            continue

        assert after_account is not None
        row["status"] = "applied"
        row["approval_id"] = approval_id
        audit_rows.append(row)
        accepted += 1
        before_stats = stats(before_account.owner_team)
        before_stats["applied_corrections"] += 1
        before_stats["net_delta_cents"] += delta
        if abs(delta) > before_account.materiality_cents:
            before_stats["material_corrections"] += 1
            material_corrections += 1
        if before_account.owner_team != after_account.owner_team:
            before_stats["moved_out_entries"] += 1
            stats(after_account.owner_team)["moved_in_entries"] += 1
            moved_entries += 1

        entry.current_account_id = after_account_id
        entry.current_posted_at = after_posted_at
        entry.current_amount_cents = after_amount

    rollup_groups: dict[tuple[str, str, str], dict[str, int]] = {}
    for entry in entries.values():
        original_account = accounts[entry.original_account_id]
        original_key = (
            _month(entry.original_posted_at),
            original_account.entity_id,
            original_account.currency,
        )
        original_group = rollup_groups.setdefault(
            original_key,
            {"gross_cents": 0, "net_cents": 0, "original_entry_count": 0, "final_entry_count": 0},
        )
        original_group["gross_cents"] += entry.original_amount_cents
        original_group["original_entry_count"] += 1

        current_account = accounts[entry.current_account_id]
        current_key = (
            _month(entry.current_posted_at),
            current_account.entity_id,
            current_account.currency,
        )
        current_group = rollup_groups.setdefault(
            current_key,
            {"gross_cents": 0, "net_cents": 0, "original_entry_count": 0, "final_entry_count": 0},
        )
        current_group["net_cents"] += entry.current_amount_cents
        current_group["final_entry_count"] += 1

    rollups: list[dict[str, object]] = []
    for month, entity_id, currency in sorted(rollup_groups):
        group = rollup_groups[(month, entity_id, currency)]
        rollups.append(
            {
                "month": month,
                "entity_id": entity_id,
                "currency": currency,
                "gross_cents": group["gross_cents"],
                "net_cents": group["net_cents"],
                "correction_delta_cents": group["net_cents"] - group["gross_cents"],
                "original_entry_count": group["original_entry_count"],
                "final_entry_count": group["final_entry_count"],
            }
        )

    owner_rows = [
        {"owner_team": owner, **values}
        for owner, values in sorted(owner_stats.items())
    ]

    _write_csv(
        output_path / "restated_rollups.csv",
        [
            "month",
            "entity_id",
            "currency",
            "gross_cents",
            "net_cents",
            "correction_delta_cents",
            "original_entry_count",
            "final_entry_count",
        ],
        rollups,
    )
    _write_csv(
        output_path / "correction_audit.csv",
        [
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
        ],
        audit_rows,
    )
    _write_csv(
        output_path / "owner_impact.csv",
        [
            "owner_team",
            "applied_corrections",
            "rejected_corrections",
            "net_delta_cents",
            "moved_in_entries",
            "moved_out_entries",
            "material_corrections",
        ],
        owner_rows,
    )

    gross_total = sum(entry.original_amount_cents for entry in entries.values())
    net_total = sum(entry.current_amount_cents for entry in entries.values())
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
    (output_path / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")
PY

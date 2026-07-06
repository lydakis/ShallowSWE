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
class Entry:
    entry_id: str
    month: str
    amount: int
    current_amount: int


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _read_entries(input_dir: Path) -> dict[str, Entry]:
    entries: dict[str, Entry] = {}
    for path in sorted((input_dir / "months").glob("*.csv")):
        for row in _read_csv(path):
            amount = int(row["amount_cents"])
            entries[row["entry_id"]] = Entry(
                entry_id=row["entry_id"],
                month=row["posted_at"][:7],
                amount=amount,
                current_amount=amount,
            )
    return entries


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def restate(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    entries = _read_entries(input_path)
    corrections = sorted(
        _read_csv(input_path / "corrections.csv"),
        key=lambda row: (row["applied_at"], row["correction_id"]),
    )

    audit_rows: list[dict[str, object]] = []
    accepted = 0
    rejected = 0
    for correction in corrections:
        target = correction["target_entry_id"]
        restated = int(correction["restated_amount_cents"])
        entry = entries.get(target)
        if entry is None:
            rejected += 1
            audit_rows.append(
                {
                    "correction_id": correction["correction_id"],
                    "target_entry_id": target,
                    "month": "",
                    "original_amount_cents": "",
                    "restated_amount_cents": restated,
                    "delta_cents": "",
                    "status": "rejected_unknown_entry",
                    "reason": correction["reason"],
                }
            )
            continue

        delta = restated - entry.current_amount
        audit_rows.append(
            {
                "correction_id": correction["correction_id"],
                "target_entry_id": target,
                "month": entry.month,
                "original_amount_cents": entry.current_amount,
                "restated_amount_cents": restated,
                "delta_cents": delta,
                "status": "applied",
                "reason": correction["reason"],
            }
        )
        entry.current_amount = restated
        accepted += 1

    months = sorted({entry.month for entry in entries.values()})
    rollups: list[dict[str, object]] = []
    for month in months:
        month_entries = [entry for entry in entries.values() if entry.month == month]
        gross = sum(entry.amount for entry in month_entries)
        net = sum(entry.current_amount for entry in month_entries)
        rollups.append(
            {
                "month": month,
                "gross_cents": gross,
                "correction_delta_cents": net - gross,
                "net_cents": net,
                "entry_count": len(month_entries),
            }
        )

    _write_csv(
        output_path / "restated_rollups.csv",
        ["month", "gross_cents", "correction_delta_cents", "net_cents", "entry_count"],
        rollups,
    )
    _write_csv(
        output_path / "correction_audit.csv",
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
        audit_rows,
    )

    gross_total = sum(entry.amount for entry in entries.values())
    net_total = sum(entry.current_amount for entry in entries.values())
    summary = {
        "months": len(months),
        "entries": len(entries),
        "accepted_corrections": accepted,
        "rejected_corrections": rejected,
        "gross_cents": gross_total,
        "correction_delta_cents": net_total - gross_total,
        "net_cents": net_total,
    }
    (output_path / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")
PY

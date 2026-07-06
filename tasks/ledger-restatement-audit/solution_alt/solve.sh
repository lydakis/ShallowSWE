#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > ledger_restate/restate.py <<'PY'
from __future__ import annotations

from pathlib import Path
from collections import defaultdict
import csv
import json


ROLLUP_FIELDS = ["month", "gross_cents", "correction_delta_cents", "net_cents", "entry_count"]
AUDIT_FIELDS = [
    "correction_id",
    "target_entry_id",
    "month",
    "original_amount_cents",
    "restated_amount_cents",
    "delta_cents",
    "status",
    "reason",
]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def restate(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    entries: dict[str, dict[str, object]] = {}
    for ledger_file in sorted((input_path / "months").glob("*.csv")):
        for row in _rows(ledger_file):
            original = int(row["amount_cents"])
            entries[row["entry_id"]] = {
                "month": row["posted_at"][:7],
                "original": original,
                "current": original,
            }

    audit: list[dict[str, object]] = []
    accepted = rejected = 0
    for correction in sorted(
        _rows(input_path / "corrections.csv"),
        key=lambda row: (row["applied_at"], row["correction_id"]),
    ):
        target = correction["target_entry_id"]
        restated = int(correction["restated_amount_cents"])
        if target not in entries:
            rejected += 1
            audit.append(
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

        entry = entries[target]
        before = int(entry["current"])
        entry["current"] = restated
        accepted += 1
        audit.append(
            {
                "correction_id": correction["correction_id"],
                "target_entry_id": target,
                "month": entry["month"],
                "original_amount_cents": before,
                "restated_amount_cents": restated,
                "delta_cents": restated - before,
                "status": "applied",
                "reason": correction["reason"],
            }
        )

    by_month: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in entries.values():
        by_month[str(entry["month"])].append(entry)

    rollups = []
    for month in sorted(by_month):
        month_entries = by_month[month]
        gross = sum(int(entry["original"]) for entry in month_entries)
        net = sum(int(entry["current"]) for entry in month_entries)
        rollups.append(
            {
                "month": month,
                "gross_cents": gross,
                "correction_delta_cents": net - gross,
                "net_cents": net,
                "entry_count": len(month_entries),
            }
        )

    _write(output_path / "restated_rollups.csv", ROLLUP_FIELDS, rollups)
    _write(output_path / "correction_audit.csv", AUDIT_FIELDS, audit)

    gross_total = sum(int(entry["original"]) for entry in entries.values())
    net_total = sum(int(entry["current"]) for entry in entries.values())
    (output_path / "summary.json").write_text(
        json.dumps(
            {
                "months": len(by_month),
                "entries": len(entries),
                "accepted_corrections": accepted,
                "rejected_corrections": rejected,
                "gross_cents": gross_total,
                "correction_delta_cents": net_total - gross_total,
                "net_cents": net_total,
            },
            sort_keys=True,
        )
        + "\n"
    )
PY

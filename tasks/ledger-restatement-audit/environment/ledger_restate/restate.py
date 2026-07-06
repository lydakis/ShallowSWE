from __future__ import annotations

from pathlib import Path
import csv
import json


def _read_month_rows(input_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((input_dir / "months").glob("*.csv")):
        with path.open(newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def restate(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    rows = _read_month_rows(input_path)
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        month = row["posted_at"][:7]
        bucket = totals.setdefault(month, {"gross": 0, "entries": 0})
        bucket["gross"] += int(row["amount_cents"])
        bucket["entries"] += 1

    with (output_path / "restated_rollups.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "month",
                "gross_cents",
                "correction_delta_cents",
                "net_cents",
                "entry_count",
            ],
        )
        writer.writeheader()
        for month, bucket in sorted(totals.items()):
            writer.writerow(
                {
                    "month": month,
                    "gross_cents": bucket["gross"],
                    "correction_delta_cents": 0,
                    "net_cents": bucket["gross"],
                    "entry_count": bucket["entries"],
                }
            )

    summary = {
        "months": len(totals),
        "entries": len(rows),
        "accepted_corrections": 0,
        "rejected_corrections": 0,
        "gross_cents": sum(bucket["gross"] for bucket in totals.values()),
        "correction_delta_cents": 0,
        "net_cents": sum(bucket["gross"] for bucket in totals.values()),
    }
    (output_path / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")

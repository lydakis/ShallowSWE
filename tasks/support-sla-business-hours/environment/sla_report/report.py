from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import json


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _elapsed_minutes(start: str, end: str) -> int:
    return int((_parse(end) - _parse(start)).total_seconds() // 60)


def write_report(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    calendar = json.loads((input_path / "calendar.json").read_text())
    thresholds = calendar["thresholds_by_priority"]

    rows: list[dict[str, str]] = []
    for ticket in sorted(_read_csv(input_path / "tickets.csv"), key=lambda row: row["ticket_id"]):
        priority = ticket["priority"]
        response_minutes = _elapsed_minutes(ticket["opened_at"], ticket["first_response_at"])
        resolution_minutes = _elapsed_minutes(ticket["opened_at"], ticket["resolved_at"])
        response_breached = response_minutes > int(thresholds[priority]["response_minutes"])
        resolution_breached = resolution_minutes > int(thresholds[priority]["resolution_minutes"])
        rows.append(
            {
                "ticket_id": ticket["ticket_id"],
                "priority": priority,
                "business_minutes_to_first_response": str(response_minutes),
                "business_minutes_to_resolution": str(resolution_minutes),
                "paused_business_minutes": "0",
                "response_breached": str(response_breached).lower(),
                "resolution_breached": str(resolution_breached).lower(),
            }
        )

    with (output_path / "ticket_sla.csv").open("w", newline="") as handle:
        fieldnames = [
            "ticket_id",
            "priority",
            "business_minutes_to_first_response",
            "business_minutes_to_resolution",
            "paused_business_minutes",
            "response_breached",
            "resolution_breached",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "tickets": len(rows),
        "response_breaches": sum(row["response_breached"] == "true" for row in rows),
        "resolution_breaches": sum(row["resolution_breached"] == "true" for row in rows),
        "any_breaches": sum(
            row["response_breached"] == "true" or row["resolution_breached"] == "true"
            for row in rows
        ),
        "total_paused_business_minutes": 0,
    }
    (output_path / "breach_summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")

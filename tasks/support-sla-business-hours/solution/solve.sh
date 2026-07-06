#!/usr/bin/env bash
set -euo pipefail

cat > sla_report/report.py <<'PY'
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import csv
import json


FIELDS = [
    "ticket_id",
    "priority",
    "business_minutes_to_first_response",
    "business_minutes_to_resolution",
    "paused_business_minutes",
    "response_breached",
    "resolution_breached",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_at(value: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(value).astimezone(tz)


def business_minutes(start: datetime, end: datetime, calendar: dict[str, object]) -> int:
    if end <= start:
        return 0
    tz = ZoneInfo(str(calendar["timezone"]))
    start = start.astimezone(tz)
    end = end.astimezone(tz)
    holidays = {date.fromisoformat(raw) for raw in calendar["holidays"]}
    start_hour, start_minute = [int(part) for part in str(calendar["business_start"]).split(":")]
    end_hour, end_minute = [int(part) for part in str(calendar["business_end"]).split(":")]
    total = 0
    current = start.date()
    while current <= end.date():
        if current.weekday() < 5 and current not in holidays:
            window_start = datetime.combine(current, time(start_hour, start_minute), tz)
            window_end = datetime.combine(current, time(end_hour, end_minute), tz)
            overlap_start = max(start, window_start)
            overlap_end = min(end, window_end)
            if overlap_end > overlap_start:
                total += int((overlap_end - overlap_start).total_seconds() // 60)
        current += timedelta(days=1)
    return total


def pause_intervals(
    ticket_id: str,
    events: list[dict[str, str]],
    resolved_at: datetime,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    intervals: list[tuple[datetime, datetime]] = []
    start: datetime | None = None
    for event in sorted(
        (row for row in events if row["ticket_id"] == ticket_id),
        key=lambda row: row["at"],
    ):
        at = parse_at(event["at"], tz)
        if event["event_type"] == "waiting_on_customer_start":
            if start is None:
                start = at
        elif event["event_type"] == "waiting_on_customer_end" and start is not None:
            intervals.append((start, at))
            start = None
    if start is not None:
        intervals.append((start, resolved_at))

    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    calendar = json.loads((input_path / "calendar.json").read_text())
    tz = ZoneInfo(str(calendar["timezone"]))
    thresholds = calendar["thresholds_by_priority"]
    events = read_csv(input_path / "events.csv")

    rows: list[dict[str, str]] = []
    for ticket in sorted(read_csv(input_path / "tickets.csv"), key=lambda row: row["ticket_id"]):
        opened = parse_at(ticket["opened_at"], tz)
        first_response = parse_at(ticket["first_response_at"], tz)
        resolved = parse_at(ticket["resolved_at"], tz)
        response_minutes = business_minutes(opened, first_response, calendar)
        raw_resolution = business_minutes(opened, resolved, calendar)
        paused = sum(
            business_minutes(max(opened, start), min(resolved, end), calendar)
            for start, end in pause_intervals(ticket["ticket_id"], events, resolved, tz)
            if end > opened and start < resolved
        )
        resolution_minutes = max(0, raw_resolution - paused)
        priority = ticket["priority"]
        response_breached = response_minutes > int(thresholds[priority]["response_minutes"])
        resolution_breached = resolution_minutes > int(thresholds[priority]["resolution_minutes"])
        rows.append(
            {
                "ticket_id": ticket["ticket_id"],
                "priority": priority,
                "business_minutes_to_first_response": str(response_minutes),
                "business_minutes_to_resolution": str(resolution_minutes),
                "paused_business_minutes": str(paused),
                "response_breached": str(response_breached).lower(),
                "resolution_breached": str(resolution_breached).lower(),
            }
        )

    write_csv(output_path / "ticket_sla.csv", rows)
    summary = {
        "tickets": len(rows),
        "response_breaches": sum(row["response_breached"] == "true" for row in rows),
        "resolution_breaches": sum(row["resolution_breached"] == "true" for row in rows),
        "any_breaches": sum(
            row["response_breached"] == "true" or row["resolution_breached"] == "true"
            for row in rows
        ),
        "total_paused_business_minutes": sum(int(row["paused_business_minutes"]) for row in rows),
    }
    (output_path / "breach_summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")
PY

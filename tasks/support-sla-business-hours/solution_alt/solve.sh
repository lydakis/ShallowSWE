#!/usr/bin/env bash
set -euo pipefail

cat > sla_report/report.py <<'PY'
from __future__ import annotations

from collections import defaultdict
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


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def local_dt(raw: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(raw).astimezone(tz)


def calendar_parts(calendar: dict[str, object]) -> tuple[ZoneInfo, set[date], time, time]:
    tz = ZoneInfo(str(calendar["timezone"]))
    holidays = {date.fromisoformat(item) for item in calendar["holidays"]}
    start = time(*[int(part) for part in str(calendar["business_start"]).split(":")])
    end = time(*[int(part) for part in str(calendar["business_end"]).split(":")])
    return tz, holidays, start, end


def minutes_between(start: datetime, end: datetime, calendar: dict[str, object]) -> int:
    if end <= start:
        return 0
    tz, holidays, opens, closes = calendar_parts(calendar)
    start = start.astimezone(tz)
    end = end.astimezone(tz)
    total = 0
    day = start.date()
    while day <= end.date():
        if day.weekday() <= 4 and day not in holidays:
            lo = max(start, datetime.combine(day, opens, tz))
            hi = min(end, datetime.combine(day, closes, tz))
            if hi > lo:
                total += int((hi - lo).total_seconds() // 60)
        day += timedelta(days=1)
    return total


def waits_by_ticket(events: list[dict[str, str]], tz: ZoneInfo) -> dict[str, list[tuple[datetime, datetime | None]]]:
    open_wait: dict[str, datetime | None] = defaultdict(lambda: None)
    waits: dict[str, list[tuple[datetime, datetime | None]]] = defaultdict(list)
    for event in sorted(events, key=lambda row: (row["ticket_id"], row["at"])):
        ticket_id = event["ticket_id"]
        at = local_dt(event["at"], tz)
        if event["event_type"] == "waiting_on_customer_start":
            if open_wait[ticket_id] is None:
                open_wait[ticket_id] = at
        elif event["event_type"] == "waiting_on_customer_end" and open_wait[ticket_id] is not None:
            waits[ticket_id].append((open_wait[ticket_id], at))
            open_wait[ticket_id] = None
    for ticket_id, start in open_wait.items():
        if start is not None:
            waits[ticket_id].append((start, None))
    return waits


def merged(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    result: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if not result or start > result[-1][1]:
            result.append((start, end))
        else:
            result[-1] = (result[-1][0], max(result[-1][1], end))
    return result


def write_report(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    calendar = json.loads((input_path / "calendar.json").read_text())
    tz = ZoneInfo(str(calendar["timezone"]))
    thresholds = calendar["thresholds_by_priority"]
    events = rows(input_path / "events.csv")
    waits = waits_by_ticket(events, tz)

    output_rows: list[dict[str, str]] = []
    for ticket in sorted(rows(input_path / "tickets.csv"), key=lambda row: row["ticket_id"]):
        opened = local_dt(ticket["opened_at"], tz)
        first = local_dt(ticket["first_response_at"], tz)
        resolved = local_dt(ticket["resolved_at"], tz)
        response = minutes_between(opened, first, calendar)
        wait_intervals = [
            (max(opened, start), min(resolved, end or resolved))
            for start, end in waits.get(ticket["ticket_id"], [])
            if (end or resolved) > opened and start < resolved
        ]
        paused = sum(minutes_between(start, end, calendar) for start, end in merged(wait_intervals))
        resolution = max(0, minutes_between(opened, resolved, calendar) - paused)
        priority = ticket["priority"]
        response_breached = response > int(thresholds[priority]["response_minutes"])
        resolution_breached = resolution > int(thresholds[priority]["resolution_minutes"])
        output_rows.append(
            {
                "ticket_id": ticket["ticket_id"],
                "priority": priority,
                "business_minutes_to_first_response": str(response),
                "business_minutes_to_resolution": str(resolution),
                "paused_business_minutes": str(paused),
                "response_breached": str(response_breached).lower(),
                "resolution_breached": str(resolution_breached).lower(),
            }
        )

    with (output_path / "ticket_sla.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "tickets": len(output_rows),
        "response_breaches": sum(row["response_breached"] == "true" for row in output_rows),
        "resolution_breaches": sum(row["resolution_breached"] == "true" for row in output_rows),
        "any_breaches": sum(
            row["response_breached"] == "true" or row["resolution_breached"] == "true"
            for row in output_rows
        ),
        "total_paused_business_minutes": sum(int(row["paused_business_minutes"]) for row in output_rows),
    }
    (output_path / "breach_summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")
PY

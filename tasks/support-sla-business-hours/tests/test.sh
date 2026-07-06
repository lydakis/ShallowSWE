#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import csv
import json
import subprocess
import sys
import tempfile
import unittest


FIELDNAMES = [
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


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_report(input_dir: Path, output_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "sla_report.cli",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
    )


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


def merged_pauses(
    ticket_id: str,
    events: list[dict[str, str]],
    resolved_at: datetime,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    raw: list[tuple[datetime, datetime]] = []
    open_start: datetime | None = None
    for event in sorted(
        [row for row in events if row["ticket_id"] == ticket_id],
        key=lambda row: row["at"],
    ):
        at = parse_at(event["at"], tz)
        if event["event_type"] == "waiting_on_customer_start":
            if open_start is None:
                open_start = at
        elif event["event_type"] == "waiting_on_customer_end" and open_start is not None:
            raw.append((open_start, at))
            open_start = None
    if open_start is not None:
        raw.append((open_start, resolved_at))

    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(raw):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def expected(input_dir: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    calendar = json.loads((input_dir / "calendar.json").read_text())
    tz = ZoneInfo(str(calendar["timezone"]))
    thresholds = calendar["thresholds_by_priority"]
    events = read_csv(input_dir / "events.csv")
    rows: list[dict[str, str]] = []
    for ticket in sorted(read_csv(input_dir / "tickets.csv"), key=lambda row: row["ticket_id"]):
        opened = parse_at(ticket["opened_at"], tz)
        first = parse_at(ticket["first_response_at"], tz)
        resolved = parse_at(ticket["resolved_at"], tz)
        response = business_minutes(opened, first, calendar)
        pause_minutes = sum(
            business_minutes(max(opened, start), min(resolved, end), calendar)
            for start, end in merged_pauses(ticket["ticket_id"], events, resolved, tz)
            if end > opened and start < resolved
        )
        raw_resolution = business_minutes(opened, resolved, calendar)
        resolution = max(0, raw_resolution - pause_minutes)
        priority = ticket["priority"]
        response_breached = response > int(thresholds[priority]["response_minutes"])
        resolution_breached = resolution > int(thresholds[priority]["resolution_minutes"])
        rows.append(
            {
                "ticket_id": ticket["ticket_id"],
                "priority": priority,
                "business_minutes_to_first_response": str(response),
                "business_minutes_to_resolution": str(resolution),
                "paused_business_minutes": str(pause_minutes),
                "response_breached": str(response_breached).lower(),
                "resolution_breached": str(resolution_breached).lower(),
            }
        )
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
    return rows, summary


def write_hidden_fixture(root: Path) -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    (input_dir / "calendar.json").write_text(
        json.dumps(
            {
                "timezone": "America/Chicago",
                "business_start": "08:30",
                "business_end": "16:30",
                "holidays": ["2026-11-26", "2026-11-27"],
                "thresholds_by_priority": {
                    "p1": {"response_minutes": 45, "resolution_minutes": 360},
                    "p2": {"response_minutes": 180, "resolution_minutes": 900},
                    "p3": {"response_minutes": 420, "resolution_minutes": 1800},
                },
            },
            indent=2,
        )
    )
    write_csv(
        input_dir / "tickets.csv",
        ["ticket_id", "priority", "opened_at", "first_response_at", "resolved_at"],
        [
            {
                "ticket_id": "H-010",
                "priority": "p1",
                "opened_at": "2026-11-25T15:45:00-06:00",
                "first_response_at": "2026-11-30T09:15:00-06:00",
                "resolved_at": "2026-11-30T12:00:00-06:00",
            },
            {
                "ticket_id": "H-020",
                "priority": "p2",
                "opened_at": "2026-11-24T10:00:00-06:00",
                "first_response_at": "2026-11-24T12:00:00-06:00",
                "resolved_at": "2026-11-30T15:00:00-06:00",
            },
            {
                "ticket_id": "H-030",
                "priority": "p3",
                "opened_at": "2026-11-25T07:30:00-06:00",
                "first_response_at": "2026-11-25T09:00:00-06:00",
                "resolved_at": "2026-12-01T09:30:00-06:00",
            },
        ],
    )
    write_csv(
        input_dir / "events.csv",
        ["ticket_id", "event_type", "at"],
        [
            {"ticket_id": "H-020", "event_type": "waiting_on_customer_start", "at": "2026-11-24T15:00:00-06:00"},
            {"ticket_id": "H-020", "event_type": "waiting_on_customer_start", "at": "2026-11-24T15:30:00-06:00"},
            {"ticket_id": "H-020", "event_type": "waiting_on_customer_end", "at": "2026-11-30T10:30:00-06:00"},
            {"ticket_id": "H-030", "event_type": "waiting_on_customer_start", "at": "2026-11-30T15:00:00-06:00"},
        ],
    )
    return input_dir


class SupportSlaBusinessHoursTests(unittest.TestCase):
    def assert_report(self, input_dir: Path, output_dir: Path) -> None:
        rows = read_csv(output_dir / "ticket_sla.csv")
        summary = json.loads((output_dir / "breach_summary.json").read_text())
        expected_rows, expected_summary = expected(input_dir)
        self.assertEqual(rows, expected_rows)
        self.assertEqual(summary, expected_summary)
        self.assertEqual(list(rows[0]), FIELDNAMES)
        self.assertEqual(
            set(summary),
            {
                "tickets",
                "response_breaches",
                "resolution_breaches",
                "any_breaches",
                "total_paused_business_minutes",
            },
        )

    def test_visible_fixture_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            run_report(Path("/app/input"), output)
            first = {
                "csv": (output / "ticket_sla.csv").read_text(),
                "json": (output / "breach_summary.json").read_text(),
            }
            run_report(Path("/app/input"), output)
            second = {
                "csv": (output / "ticket_sla.csv").read_text(),
                "json": (output / "breach_summary.json").read_text(),
            }
            self.assertEqual(first, second)
            self.assert_report(Path("/app/input"), output)

    def test_hidden_fixture_exercises_holidays_merged_waits_and_open_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = write_hidden_fixture(root)
            output = root / "out"
            run_report(input_dir, output)
            self.assert_report(input_dir, output)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SupportSlaBusinessHoursTests)
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

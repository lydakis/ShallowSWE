#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import csv
import json
import subprocess
import sys
import tempfile
import unittest


TICKET_FIELDS = [
    "ticket_id",
    "account_id",
    "priority",
    "segment",
    "owner_team",
    "business_minutes_to_first_response",
    "business_minutes_to_resolution",
    "paused_business_minutes",
    "outage_exempt_response_minutes",
    "outage_exempt_resolution_minutes",
    "effective_response_threshold",
    "effective_resolution_threshold",
    "response_breached",
    "resolution_breached",
    "credit_cents",
    "review_required",
    "breach_reasons",
]
ACCOUNT_FIELDS = [
    "account_id",
    "segment",
    "tickets",
    "response_breaches",
    "resolution_breaches",
    "credits_cents",
    "review_required",
    "worst_priority",
    "total_paused_business_minutes",
    "total_outage_exempt_minutes",
]
ESCALATION_FIELDS = [
    "ticket_id",
    "escalation_count",
    "escalation_business_minutes",
    "open_escalation",
    "owners",
    "review_required",
    "breach_reasons",
]
SUMMARY_KEYS = {
    "tickets",
    "accounts",
    "response_breaches",
    "resolution_breaches",
    "any_breaches",
    "credits_cents",
    "review_required_accounts",
    "total_paused_business_minutes",
    "total_outage_exempt_minutes",
    "breached_ticket_ids",
    "generated_for_timezone",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_bool(raw: str) -> bool:
    return raw.strip().lower() == "true"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def parse_at(raw: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(raw).astimezone(tz)


def calendar_parts(calendar: dict[str, object]) -> tuple[ZoneInfo, set[date], time, time]:
    tz = ZoneInfo(str(calendar["timezone"]))
    holidays = {date.fromisoformat(str(raw)) for raw in calendar["holidays"]}
    start = time(*[int(part) for part in str(calendar["business_start"]).split(":")])
    end = time(*[int(part) for part in str(calendar["business_end"]).split(":")])
    return tz, holidays, start, end


def business_minutes(start: datetime, end: datetime, calendar: dict[str, object]) -> int:
    if end <= start:
        return 0
    tz, holidays, start_time, end_time = calendar_parts(calendar)
    start = start.astimezone(tz)
    end = end.astimezone(tz)
    total = 0
    cursor = start.date()
    while cursor <= end.date():
        if cursor.weekday() < 5 and cursor not in holidays:
            lo = max(start, datetime.combine(cursor, start_time, tz))
            hi = min(end, datetime.combine(cursor, end_time, tz))
            if hi > lo:
                total += int((hi - lo).total_seconds() // 60)
        cursor += timedelta(days=1)
    return total


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted((s, e) for s, e in intervals if e > s):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def waiting_intervals(
    ticket_id: str,
    events: list[dict[str, str]],
    resolved_at: datetime,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    intervals: list[tuple[datetime, datetime]] = []
    open_start: datetime | None = None
    for event in sorted(
        (row for row in events if row["ticket_id"] == ticket_id),
        key=lambda row: row["at"],
    ):
        at = parse_at(event["at"], tz)
        if event["event_type"] == "waiting_on_customer_start":
            if open_start is None:
                open_start = at
        elif event["event_type"] == "waiting_on_customer_end" and open_start is not None:
            intervals.append((open_start, at))
            open_start = None
    if open_start is not None:
        intervals.append((open_start, resolved_at))
    return merge_intervals(intervals)


def outage_minutes(
    account_id: str,
    outages: list[dict[str, str]],
    start: datetime,
    end: datetime,
    flag: str,
    calendar: dict[str, object],
    tz: ZoneInfo,
) -> int:
    overlaps: list[tuple[datetime, datetime]] = []
    for outage in outages:
        if outage["account_id"] != account_id or not parse_bool(outage[flag]):
            continue
        lo = max(start, parse_at(outage["start_at"], tz))
        hi = min(end, parse_at(outage["end_at"], tz))
        overlaps.append((lo, hi))
    return sum(business_minutes(lo, hi, calendar) for lo, hi in merge_intervals(overlaps))


def escalation_details(
    ticket_id: str,
    escalations: list[dict[str, str]],
    opened: datetime,
    resolved: datetime,
    calendar: dict[str, object],
    tz: ZoneInfo,
) -> dict[str, object]:
    ticket_rows = [row for row in escalations if row["ticket_id"] == ticket_id]
    owners: set[str] = set()
    minutes = 0
    open_escalation = False
    for row in ticket_rows:
        start = max(opened, parse_at(row["opened_at"], tz))
        if row["closed_at"].strip():
            end = min(resolved, parse_at(row["closed_at"], tz))
        else:
            end = resolved
            open_escalation = True
        if row["owner"].strip():
            owners.add(row["owner"].strip())
        minutes += business_minutes(start, end, calendar)
    return {
        "count": len(ticket_rows),
        "minutes": minutes,
        "open": open_escalation,
        "owners": "|".join(sorted(owners)),
    }


def priority_key(priority: str) -> tuple[int, str]:
    return ({"p1": 1, "p2": 2, "p3": 3}.get(priority, 99), priority)


def expected(input_dir: Path) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, object],
]:
    calendar = json.loads((input_dir / "calendar.json").read_text())
    tz = ZoneInfo(str(calendar["timezone"]))
    thresholds = calendar["thresholds_by_priority"]
    tickets = read_csv(input_dir / "tickets.csv")
    events = read_csv(input_dir / "events.csv")
    accounts = {row["account_id"]: row for row in read_csv(input_dir / "accounts.csv")}
    entitlements = {row["segment"]: row for row in read_csv(input_dir / "entitlements.csv")}
    outages = read_csv(input_dir / "outage_windows.csv")
    escalations = read_csv(input_dir / "escalations.csv")

    ticket_rows: list[dict[str, str]] = []
    escalation_rows: list[dict[str, str]] = []
    for ticket in sorted(tickets, key=lambda row: row["ticket_id"]):
        account = accounts[ticket["account_id"]]
        entitlement = entitlements[account["segment"]]
        opened = parse_at(ticket["opened_at"], tz)
        first = parse_at(ticket["first_response_at"], tz)
        resolved = parse_at(ticket["resolved_at"], tz)
        raw_response = business_minutes(opened, first, calendar)
        raw_resolution = business_minutes(opened, resolved, calendar)
        paused = sum(
            business_minutes(max(opened, start), min(resolved, end), calendar)
            for start, end in waiting_intervals(ticket["ticket_id"], events, resolved, tz)
            if end > opened and start < resolved
        )
        response_exempt = outage_minutes(
            ticket["account_id"], outages, opened, first, "exempt_response", calendar, tz
        )
        resolution_exempt = outage_minutes(
            ticket["account_id"], outages, opened, resolved, "exempt_resolution", calendar, tz
        )
        response = max(0, raw_response - response_exempt)
        resolution = max(0, raw_resolution - paused - resolution_exempt)
        priority = ticket["priority"]
        response_threshold = int(
            int(thresholds[priority]["response_minutes"]) * float(entitlement["response_multiplier"])
        )
        resolution_threshold = int(
            int(thresholds[priority]["resolution_minutes"])
            * float(entitlement["resolution_multiplier"])
        )
        response_breached = response > response_threshold
        resolution_breached = resolution > resolution_threshold
        escalation = escalation_details(ticket["ticket_id"], escalations, opened, resolved, calendar, tz)
        reasons: list[str] = []
        if response_breached:
            reasons.append("response")
        if resolution_breached:
            reasons.append("resolution")
        if escalation["open"]:
            reasons.append("open_escalation")
        credit = 0
        if response_breached:
            credit += int(entitlement["response_credit_cents"])
        if resolution_breached:
            credit += int(entitlement["resolution_credit_cents"])
        review = (
            (parse_bool(entitlement["executive_review"]) and bool(reasons))
            or (priority == "p1" and resolution_breached)
            or bool(escalation["open"])
        )
        row = {
            "ticket_id": ticket["ticket_id"],
            "account_id": ticket["account_id"],
            "priority": priority,
            "segment": account["segment"],
            "owner_team": ticket["owner_team"],
            "business_minutes_to_first_response": str(response),
            "business_minutes_to_resolution": str(resolution),
            "paused_business_minutes": str(paused),
            "outage_exempt_response_minutes": str(response_exempt),
            "outage_exempt_resolution_minutes": str(resolution_exempt),
            "effective_response_threshold": str(response_threshold),
            "effective_resolution_threshold": str(resolution_threshold),
            "response_breached": bool_text(response_breached),
            "resolution_breached": bool_text(resolution_breached),
            "credit_cents": str(credit),
            "review_required": bool_text(review),
            "breach_reasons": "|".join(reasons),
        }
        ticket_rows.append(row)
        if escalation["count"] or reasons:
            escalation_rows.append(
                {
                    "ticket_id": ticket["ticket_id"],
                    "escalation_count": str(escalation["count"]),
                    "escalation_business_minutes": str(escalation["minutes"]),
                    "open_escalation": bool_text(bool(escalation["open"])),
                    "owners": str(escalation["owners"]),
                    "review_required": bool_text(review),
                    "breach_reasons": "|".join(reasons),
                }
            )

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ticket_rows:
        grouped[row["account_id"]].append(row)
    account_rows: list[dict[str, str]] = []
    for account_id in sorted(grouped):
        rows = grouped[account_id]
        account_rows.append(
            {
                "account_id": account_id,
                "segment": rows[0]["segment"],
                "tickets": str(len(rows)),
                "response_breaches": str(sum(row["response_breached"] == "true" for row in rows)),
                "resolution_breaches": str(sum(row["resolution_breached"] == "true" for row in rows)),
                "credits_cents": str(sum(int(row["credit_cents"]) for row in rows)),
                "review_required": bool_text(any(row["review_required"] == "true" for row in rows)),
                "worst_priority": min((row["priority"] for row in rows), key=priority_key),
                "total_paused_business_minutes": str(
                    sum(int(row["paused_business_minutes"]) for row in rows)
                ),
                "total_outage_exempt_minutes": str(
                    sum(
                        int(row["outage_exempt_response_minutes"])
                        + int(row["outage_exempt_resolution_minutes"])
                        for row in rows
                    )
                ),
            }
        )

    summary = {
        "tickets": len(ticket_rows),
        "accounts": len(account_rows),
        "response_breaches": sum(row["response_breached"] == "true" for row in ticket_rows),
        "resolution_breaches": sum(row["resolution_breached"] == "true" for row in ticket_rows),
        "any_breaches": sum(bool(row["breach_reasons"]) for row in ticket_rows),
        "credits_cents": sum(int(row["credit_cents"]) for row in ticket_rows),
        "review_required_accounts": sum(row["review_required"] == "true" for row in account_rows),
        "total_paused_business_minutes": sum(
            int(row["paused_business_minutes"]) for row in ticket_rows
        ),
        "total_outage_exempt_minutes": sum(
            int(row["outage_exempt_response_minutes"])
            + int(row["outage_exempt_resolution_minutes"])
            for row in ticket_rows
        ),
        "breached_ticket_ids": [row["ticket_id"] for row in ticket_rows if row["breach_reasons"]],
        "generated_for_timezone": str(calendar["timezone"]),
    }
    return ticket_rows, account_rows, escalation_rows, summary


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


def write_hidden_fixture(root: Path) -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    (input_dir / "calendar.json").write_text(
        json.dumps(
            {
                "timezone": "America/Denver",
                "business_start": "08:00",
                "business_end": "16:00",
                "holidays": ["2026-12-24"],
                "thresholds_by_priority": {
                    "p1": {"response_minutes": 30, "resolution_minutes": 300},
                    "p2": {"response_minutes": 180, "resolution_minutes": 780},
                    "p3": {"response_minutes": 360, "resolution_minutes": 1440},
                },
            },
            indent=2,
        )
    )
    write_csv(
        input_dir / "accounts.csv",
        ["account_id", "segment", "region", "success_manager"],
        [
            {"account_id": "H-A", "segment": "enterprise", "region": "west", "success_manager": "li"},
            {"account_id": "H-B", "segment": "growth", "region": "central", "success_manager": "noor"},
            {"account_id": "H-C", "segment": "standard", "region": "east", "success_manager": "ava"},
        ],
    )
    write_csv(
        input_dir / "entitlements.csv",
        [
            "segment",
            "response_multiplier",
            "resolution_multiplier",
            "response_credit_cents",
            "resolution_credit_cents",
            "executive_review",
        ],
        [
            {
                "segment": "enterprise",
                "response_multiplier": "0.5",
                "resolution_multiplier": "0.5",
                "response_credit_cents": "6000",
                "resolution_credit_cents": "15000",
                "executive_review": "true",
            },
            {
                "segment": "growth",
                "response_multiplier": "1.0",
                "resolution_multiplier": "0.75",
                "response_credit_cents": "3000",
                "resolution_credit_cents": "9000",
                "executive_review": "false",
            },
            {
                "segment": "standard",
                "response_multiplier": "1.25",
                "resolution_multiplier": "1.0",
                "response_credit_cents": "1000",
                "resolution_credit_cents": "4000",
                "executive_review": "false",
            },
        ],
    )
    write_csv(
        input_dir / "tickets.csv",
        [
            "ticket_id",
            "account_id",
            "priority",
            "channel",
            "opened_at",
            "first_response_at",
            "resolved_at",
            "owner_team",
        ],
        [
            {
                "ticket_id": "H-100",
                "account_id": "H-A",
                "priority": "p1",
                "channel": "email",
                "opened_at": "2026-12-23T15:00:00-07:00",
                "first_response_at": "2026-12-28T09:30:00-07:00",
                "resolved_at": "2026-12-28T15:30:00-07:00",
                "owner_team": "premier",
            },
            {
                "ticket_id": "H-200",
                "account_id": "H-B",
                "priority": "p2",
                "channel": "chat",
                "opened_at": "2026-12-23T09:15:00-07:00",
                "first_response_at": "2026-12-23T10:45:00-07:00",
                "resolved_at": "2026-12-28T14:45:00-07:00",
                "owner_team": "support",
            },
            {
                "ticket_id": "H-300",
                "account_id": "H-C",
                "priority": "p3",
                "channel": "email",
                "opened_at": "2026-12-23T07:00:00-07:00",
                "first_response_at": "2026-12-23T12:00:00-07:00",
                "resolved_at": "2026-12-29T10:00:00-07:00",
                "owner_team": "support",
            },
        ],
    )
    write_csv(
        input_dir / "events.csv",
        ["ticket_id", "event_type", "at"],
        [
            {"ticket_id": "H-200", "event_type": "waiting_on_customer_start", "at": "2026-12-23T15:00:00-07:00"},
            {"ticket_id": "H-200", "event_type": "waiting_on_customer_start", "at": "2026-12-23T15:30:00-07:00"},
            {"ticket_id": "H-200", "event_type": "waiting_on_customer_end", "at": "2026-12-28T09:00:00-07:00"},
            {"ticket_id": "H-300", "event_type": "waiting_on_customer_start", "at": "2026-12-28T13:00:00-07:00"},
        ],
    )
    write_csv(
        input_dir / "outage_windows.csv",
        ["outage_id", "account_id", "start_at", "end_at", "exempt_response", "exempt_resolution"],
        [
            {
                "outage_id": "HO-1",
                "account_id": "H-A",
                "start_at": "2026-12-23T15:15:00-07:00",
                "end_at": "2026-12-23T16:00:00-07:00",
                "exempt_response": "true",
                "exempt_resolution": "true",
            },
            {
                "outage_id": "HO-2",
                "account_id": "H-C",
                "start_at": "2026-12-28T08:00:00-07:00",
                "end_at": "2026-12-28T12:30:00-07:00",
                "exempt_response": "false",
                "exempt_resolution": "true",
            },
        ],
    )
    write_csv(
        input_dir / "escalations.csv",
        ["ticket_id", "escalation_level", "opened_at", "closed_at", "owner"],
        [
            {
                "ticket_id": "H-100",
                "escalation_level": "exec",
                "opened_at": "2026-12-28T10:00:00-07:00",
                "closed_at": "",
                "owner": "li",
            },
            {
                "ticket_id": "H-200",
                "escalation_level": "lead",
                "opened_at": "2026-12-28T09:30:00-07:00",
                "closed_at": "2026-12-28T11:00:00-07:00",
                "owner": "noor",
            },
        ],
    )
    return input_dir


class SupportSlaPackageTests(unittest.TestCase):
    def assert_package(self, input_dir: Path, output_dir: Path) -> None:
        expected_tickets, expected_accounts, expected_escalations, expected_summary = expected(input_dir)
        ticket_rows = read_csv(output_dir / "ticket_sla.csv")
        account_rows = read_csv(output_dir / "account_sla_summary.csv")
        escalation_rows = read_csv(output_dir / "escalation_audit.csv")
        summary = json.loads((output_dir / "breach_summary.json").read_text())
        self.assertEqual(ticket_rows, expected_tickets)
        self.assertEqual(account_rows, expected_accounts)
        self.assertEqual(escalation_rows, expected_escalations)
        self.assertEqual(summary, expected_summary)
        self.assertEqual(list(ticket_rows[0]), TICKET_FIELDS)
        self.assertEqual(list(account_rows[0]), ACCOUNT_FIELDS)
        self.assertEqual(list(escalation_rows[0]), ESCALATION_FIELDS)
        self.assertEqual(set(summary), SUMMARY_KEYS)

    def test_visible_fixture_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            run_report(Path("/app/input"), output)
            first = {
                name: (output / name).read_text()
                for name in [
                    "ticket_sla.csv",
                    "account_sla_summary.csv",
                    "escalation_audit.csv",
                    "breach_summary.json",
                ]
            }
            run_report(Path("/app/input"), output)
            second = {
                name: (output / name).read_text()
                for name in [
                    "ticket_sla.csv",
                    "account_sla_summary.csv",
                    "escalation_audit.csv",
                    "breach_summary.json",
                ]
            }
            self.assertEqual(first, second)
            self.assert_package(Path("/app/input"), output)

    def test_hidden_fixture_exercises_cross_file_entitlements_and_exemptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = write_hidden_fixture(root)
            output = root / "out"
            run_report(input_dir, output)
            self.assert_package(input_dir, output)
            tickets = {row["ticket_id"]: row for row in read_csv(output / "ticket_sla.csv")}
            self.assertEqual(tickets["H-100"]["effective_response_threshold"], "15")
            self.assertGreater(int(tickets["H-100"]["outage_exempt_response_minutes"]), 0)
            self.assertEqual(tickets["H-100"]["review_required"], "true")
            self.assertIn("open_escalation", tickets["H-100"]["breach_reasons"])
            self.assertGreater(int(tickets["H-200"]["paused_business_minutes"]), 0)
            self.assertGreater(int(tickets["H-300"]["outage_exempt_resolution_minutes"]), 0)
            escalations = {row["ticket_id"]: row for row in read_csv(output / "escalation_audit.csv")}
            self.assertEqual(escalations["H-100"]["open_escalation"], "true")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SupportSlaPackageTests)
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

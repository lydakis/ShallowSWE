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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def bool_text(value: object) -> str:
    return "true" if bool(value) else "false"


def parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def local_dt(value: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(value).astimezone(tz)


def calendar_parts(calendar: dict[str, object]) -> tuple[ZoneInfo, set[date], time, time]:
    tz = ZoneInfo(str(calendar["timezone"]))
    holidays = {date.fromisoformat(str(raw)) for raw in calendar["holidays"]}
    start = time(*[int(part) for part in str(calendar["business_start"]).split(":")])
    end = time(*[int(part) for part in str(calendar["business_end"]).split(":")])
    return tz, holidays, start, end


def business_minutes(start: datetime, end: datetime, calendar: dict[str, object]) -> int:
    if end <= start:
        return 0
    tz, holidays, opens, closes = calendar_parts(calendar)
    start = start.astimezone(tz)
    end = end.astimezone(tz)
    total = 0
    cursor = start.date()
    while cursor <= end.date():
        if cursor.weekday() < 5 and cursor not in holidays:
            lo = max(start, datetime.combine(cursor, opens, tz))
            hi = min(end, datetime.combine(cursor, closes, tz))
            if hi > lo:
                total += int((hi - lo).total_seconds() // 60)
        cursor += timedelta(days=1)
    return total


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def waiting_intervals(
    ticket_id: str,
    events: list[dict[str, str]],
    resolved_at: datetime,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    intervals: list[tuple[datetime, datetime]] = []
    current_start: datetime | None = None
    for event in sorted(
        (row for row in events if row["ticket_id"] == ticket_id),
        key=lambda row: row["at"],
    ):
        at = local_dt(event["at"], tz)
        if event["event_type"] == "waiting_on_customer_start":
            if current_start is None:
                current_start = at
        elif event["event_type"] == "waiting_on_customer_end" and current_start is not None:
            intervals.append((current_start, at))
            current_start = None
    if current_start is not None:
        intervals.append((current_start, resolved_at))
    return merge_intervals(intervals)


def outage_minutes(
    account_id: str,
    outages: list[dict[str, str]],
    interval_start: datetime,
    interval_end: datetime,
    flag: str,
    calendar: dict[str, object],
    tz: ZoneInfo,
) -> int:
    intervals: list[tuple[datetime, datetime]] = []
    for outage in outages:
        if outage["account_id"] != account_id or not parse_bool(outage[flag]):
            continue
        start = max(interval_start, local_dt(outage["start_at"], tz))
        end = min(interval_end, local_dt(outage["end_at"], tz))
        if end > start:
            intervals.append((start, end))
    return sum(business_minutes(start, end, calendar) for start, end in merge_intervals(intervals))


def escalation_details(
    ticket_id: str,
    rows: list[dict[str, str]],
    opened: datetime,
    resolved: datetime,
    calendar: dict[str, object],
    tz: ZoneInfo,
) -> dict[str, object]:
    ticket_rows = [row for row in rows if row["ticket_id"] == ticket_id]
    minutes = 0
    owners: set[str] = set()
    open_escalation = False
    for row in ticket_rows:
        start = max(opened, local_dt(row["opened_at"], tz))
        if row["closed_at"].strip():
            end = min(resolved, local_dt(row["closed_at"], tz))
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
    ranks = {"p1": 1, "p2": 2, "p3": 3}
    return (ranks.get(priority, 99), priority)


def write_report(input_dir: str | Path, output_dir: str | Path) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    calendar = json.loads((input_path / "calendar.json").read_text())
    tz = ZoneInfo(str(calendar["timezone"]))
    thresholds = calendar["thresholds_by_priority"]
    tickets = read_csv(input_path / "tickets.csv")
    events = read_csv(input_path / "events.csv")
    accounts = {row["account_id"]: row for row in read_csv(input_path / "accounts.csv")}
    entitlements = {row["segment"]: row for row in read_csv(input_path / "entitlements.csv")}
    outages = read_csv(input_path / "outage_windows.csv")
    escalations = read_csv(input_path / "escalations.csv")

    ticket_rows: list[dict[str, str]] = []
    escalation_rows: list[dict[str, str]] = []

    for ticket in sorted(tickets, key=lambda row: row["ticket_id"]):
        account = accounts[ticket["account_id"]]
        entitlement = entitlements[account["segment"]]
        opened = local_dt(ticket["opened_at"], tz)
        first = local_dt(ticket["first_response_at"], tz)
        resolved = local_dt(ticket["resolved_at"], tz)

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

        response_minutes = max(0, raw_response - response_exempt)
        resolution_minutes = max(0, raw_resolution - paused - resolution_exempt)
        priority = ticket["priority"]
        response_threshold = int(
            int(thresholds[priority]["response_minutes"]) * float(entitlement["response_multiplier"])
        )
        resolution_threshold = int(
            int(thresholds[priority]["resolution_minutes"])
            * float(entitlement["resolution_multiplier"])
        )
        response_breached = response_minutes > response_threshold
        resolution_breached = resolution_minutes > resolution_threshold
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
        review_required = (
            (parse_bool(entitlement["executive_review"]) and bool(reasons))
            or (priority == "p1" and resolution_breached)
            or bool(escalation["open"])
        )
        output_row = {
            "ticket_id": ticket["ticket_id"],
            "account_id": ticket["account_id"],
            "priority": priority,
            "segment": account["segment"],
            "owner_team": ticket["owner_team"],
            "business_minutes_to_first_response": str(response_minutes),
            "business_minutes_to_resolution": str(resolution_minutes),
            "paused_business_minutes": str(paused),
            "outage_exempt_response_minutes": str(response_exempt),
            "outage_exempt_resolution_minutes": str(resolution_exempt),
            "effective_response_threshold": str(response_threshold),
            "effective_resolution_threshold": str(resolution_threshold),
            "response_breached": bool_text(response_breached),
            "resolution_breached": bool_text(resolution_breached),
            "credit_cents": str(credit),
            "review_required": bool_text(review_required),
            "breach_reasons": "|".join(reasons),
        }
        ticket_rows.append(output_row)
        if escalation["count"] or reasons:
            escalation_rows.append(
                {
                    "ticket_id": ticket["ticket_id"],
                    "escalation_count": str(escalation["count"]),
                    "escalation_business_minutes": str(escalation["minutes"]),
                    "open_escalation": bool_text(escalation["open"]),
                    "owners": str(escalation["owners"]),
                    "review_required": bool_text(review_required),
                    "breach_reasons": "|".join(reasons),
                }
            )

    by_account: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ticket_rows:
        by_account[row["account_id"]].append(row)

    account_rows: list[dict[str, str]] = []
    for account_id in sorted(by_account):
        rows = by_account[account_id]
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

    write_csv(output_path / "ticket_sla.csv", TICKET_FIELDS, ticket_rows)
    write_csv(output_path / "account_sla_summary.csv", ACCOUNT_FIELDS, account_rows)
    write_csv(output_path / "escalation_audit.csv", ESCALATION_FIELDS, escalation_rows)

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
        "breached_ticket_ids": [
            row["ticket_id"] for row in ticket_rows if row["breach_reasons"]
        ],
        "generated_for_timezone": str(calendar["timezone"]),
    }
    (output_path / "breach_summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")
PY

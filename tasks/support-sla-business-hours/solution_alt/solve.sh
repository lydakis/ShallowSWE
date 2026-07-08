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


TICKET_FIELDS = "ticket_id,account_id,priority,segment,owner_team,business_minutes_to_first_response,business_minutes_to_resolution,paused_business_minutes,outage_exempt_response_minutes,outage_exempt_resolution_minutes,effective_response_threshold,effective_resolution_threshold,response_breached,resolution_breached,credit_cents,review_required,breach_reasons".split(",")
ACCOUNT_FIELDS = "account_id,segment,tickets,response_breaches,resolution_breaches,credits_cents,review_required,worst_priority,total_paused_business_minutes,total_outage_exempt_minutes".split(",")
ESCALATION_FIELDS = "ticket_id,escalation_count,escalation_business_minutes,open_escalation,owners,review_required,breach_reasons".split(",")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def out_bool(value: bool) -> str:
    return "true" if value else "false"


def parse_time(raw: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(raw).astimezone(tz)


def window_parts(calendar: dict[str, object]) -> tuple[ZoneInfo, set[date], time, time]:
    tz = ZoneInfo(str(calendar["timezone"]))
    holidays = {date.fromisoformat(str(item)) for item in calendar["holidays"]}
    start = time(*map(int, str(calendar["business_start"]).split(":")))
    end = time(*map(int, str(calendar["business_end"]).split(":")))
    return tz, holidays, start, end


def minutes(start: datetime, end: datetime, calendar: dict[str, object]) -> int:
    if end <= start:
        return 0
    tz, holidays, opens, closes = window_parts(calendar)
    start = start.astimezone(tz)
    end = end.astimezone(tz)
    total = 0
    day = start.date()
    while day <= end.date():
        if day.weekday() < 5 and day not in holidays:
            lo = max(start, datetime.combine(day, opens, tz))
            hi = min(end, datetime.combine(day, closes, tz))
            if hi > lo:
                total += int((hi - lo).total_seconds() // 60)
        day += timedelta(days=1)
    return total


def merged(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    result: list[tuple[datetime, datetime]] = []
    for start, end in sorted((s, e) for s, e in intervals if e > s):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def wait_minutes(ticket_id: str, rows: list[dict[str, str]], opened: datetime, resolved: datetime, calendar: dict[str, object], tz: ZoneInfo) -> int:
    intervals: list[tuple[datetime, datetime]] = []
    start: datetime | None = None
    for row in sorted([r for r in rows if r["ticket_id"] == ticket_id], key=lambda r: r["at"]):
        at = parse_time(row["at"], tz)
        if row["event_type"] == "waiting_on_customer_start" and start is None:
            start = at
        elif row["event_type"] == "waiting_on_customer_end" and start is not None:
            intervals.append((max(opened, start), min(resolved, at)))
            start = None
    if start is not None:
        intervals.append((max(opened, start), resolved))
    return sum(minutes(s, e, calendar) for s, e in merged(intervals))


def outage_exempt(account_id: str, rows: list[dict[str, str]], start: datetime, end: datetime, flag: str, calendar: dict[str, object], tz: ZoneInfo) -> int:
    intervals = []
    for row in rows:
        if row["account_id"] == account_id and as_bool(row[flag]):
            intervals.append((max(start, parse_time(row["start_at"], tz)), min(end, parse_time(row["end_at"], tz))))
    return sum(minutes(s, e, calendar) for s, e in merged(intervals))


def escalation(ticket_id: str, rows: list[dict[str, str]], opened: datetime, resolved: datetime, calendar: dict[str, object], tz: ZoneInfo) -> tuple[int, int, bool, str]:
    count = 0
    total = 0
    open_seen = False
    owners: set[str] = set()
    for row in rows:
        if row["ticket_id"] != ticket_id:
            continue
        count += 1
        owners.add(row["owner"])
        start = max(opened, parse_time(row["opened_at"], tz))
        if row["closed_at"].strip():
            end = min(resolved, parse_time(row["closed_at"], tz))
        else:
            end = resolved
            open_seen = True
        total += minutes(start, end, calendar)
    return count, total, open_seen, "|".join(sorted(owner for owner in owners if owner))


def priority_key(priority: str) -> tuple[int, str]:
    return ({"p1": 1, "p2": 2, "p3": 3}.get(priority, 99), priority)


def write_report(input_dir: str | Path, output_dir: str | Path) -> None:
    source = Path(input_dir)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    calendar = json.loads((source / "calendar.json").read_text())
    tz = ZoneInfo(str(calendar["timezone"]))
    thresholds = calendar["thresholds_by_priority"]
    accounts = {row["account_id"]: row for row in read_rows(source / "accounts.csv")}
    entitlements = {row["segment"]: row for row in read_rows(source / "entitlements.csv")}
    events = read_rows(source / "events.csv")
    outages = read_rows(source / "outage_windows.csv")
    escalations = read_rows(source / "escalations.csv")

    ticket_output: list[dict[str, str]] = []
    escalation_output: list[dict[str, str]] = []
    for ticket in sorted(read_rows(source / "tickets.csv"), key=lambda r: r["ticket_id"]):
        opened = parse_time(ticket["opened_at"], tz)
        first = parse_time(ticket["first_response_at"], tz)
        resolved = parse_time(ticket["resolved_at"], tz)
        account = accounts[ticket["account_id"]]
        entitlement = entitlements[account["segment"]]
        paused = wait_minutes(ticket["ticket_id"], events, opened, resolved, calendar, tz)
        response_exempt = outage_exempt(ticket["account_id"], outages, opened, first, "exempt_response", calendar, tz)
        resolution_exempt = outage_exempt(ticket["account_id"], outages, opened, resolved, "exempt_resolution", calendar, tz)
        response = max(0, minutes(opened, first, calendar) - response_exempt)
        resolution = max(0, minutes(opened, resolved, calendar) - paused - resolution_exempt)
        priority = ticket["priority"]
        response_threshold = int(int(thresholds[priority]["response_minutes"]) * float(entitlement["response_multiplier"]))
        resolution_threshold = int(int(thresholds[priority]["resolution_minutes"]) * float(entitlement["resolution_multiplier"]))
        response_breach = response > response_threshold
        resolution_breach = resolution > resolution_threshold
        count, escalation_minutes, open_escalation, owners = escalation(ticket["ticket_id"], escalations, opened, resolved, calendar, tz)
        reasons = []
        if response_breach:
            reasons.append("response")
        if resolution_breach:
            reasons.append("resolution")
        if open_escalation:
            reasons.append("open_escalation")
        credit = (int(entitlement["response_credit_cents"]) if response_breach else 0) + (
            int(entitlement["resolution_credit_cents"]) if resolution_breach else 0
        )
        review = (as_bool(entitlement["executive_review"]) and bool(reasons)) or (
            priority == "p1" and resolution_breach
        ) or open_escalation
        breach_reasons = "|".join(reasons)
        ticket_output.append(
            {
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
                "response_breached": out_bool(response_breach),
                "resolution_breached": out_bool(resolution_breach),
                "credit_cents": str(credit),
                "review_required": out_bool(review),
                "breach_reasons": breach_reasons,
            }
        )
        if count or breach_reasons:
            escalation_output.append(
                {
                    "ticket_id": ticket["ticket_id"],
                    "escalation_count": str(count),
                    "escalation_business_minutes": str(escalation_minutes),
                    "open_escalation": out_bool(open_escalation),
                    "owners": owners,
                    "review_required": out_bool(review),
                    "breach_reasons": breach_reasons,
                }
            )

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ticket_output:
        grouped[row["account_id"]].append(row)
    account_output = []
    for account_id in sorted(grouped):
        rows = grouped[account_id]
        account_output.append(
            {
                "account_id": account_id,
                "segment": rows[0]["segment"],
                "tickets": str(len(rows)),
                "response_breaches": str(sum(row["response_breached"] == "true" for row in rows)),
                "resolution_breaches": str(sum(row["resolution_breached"] == "true" for row in rows)),
                "credits_cents": str(sum(int(row["credit_cents"]) for row in rows)),
                "review_required": out_bool(any(row["review_required"] == "true" for row in rows)),
                "worst_priority": min((row["priority"] for row in rows), key=priority_key),
                "total_paused_business_minutes": str(sum(int(row["paused_business_minutes"]) for row in rows)),
                "total_outage_exempt_minutes": str(sum(int(row["outage_exempt_response_minutes"]) + int(row["outage_exempt_resolution_minutes"]) for row in rows)),
            }
        )

    write_rows(target / "ticket_sla.csv", TICKET_FIELDS, ticket_output)
    write_rows(target / "account_sla_summary.csv", ACCOUNT_FIELDS, account_output)
    write_rows(target / "escalation_audit.csv", ESCALATION_FIELDS, escalation_output)
    summary = {
        "tickets": len(ticket_output),
        "accounts": len(account_output),
        "response_breaches": sum(row["response_breached"] == "true" for row in ticket_output),
        "resolution_breaches": sum(row["resolution_breached"] == "true" for row in ticket_output),
        "any_breaches": sum(bool(row["breach_reasons"]) for row in ticket_output),
        "credits_cents": sum(int(row["credit_cents"]) for row in ticket_output),
        "review_required_accounts": sum(row["review_required"] == "true" for row in account_output),
        "total_paused_business_minutes": sum(int(row["paused_business_minutes"]) for row in ticket_output),
        "total_outage_exempt_minutes": sum(int(row["outage_exempt_response_minutes"]) + int(row["outage_exempt_resolution_minutes"]) for row in ticket_output),
        "breached_ticket_ids": [row["ticket_id"] for row in ticket_output if row["breach_reasons"]],
        "generated_for_timezone": str(calendar["timezone"]),
    }
    (target / "breach_summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")
PY

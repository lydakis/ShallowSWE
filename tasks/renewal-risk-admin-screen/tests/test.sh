#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

app = Path(os.environ.get("APP_DIR", "/app"))

RISK_FIELDS = {
    "account",
    "owner",
    "segment",
    "arr",
    "days_to_renewal",
    "seat_utilization_pct",
    "open_critical_tickets",
    "concession_days_remaining",
    "days_since_contact",
    "overdue_plan_items",
    "risk_level",
    "risk_reasons",
    "recommended_action",
}
CONCESSION_FIELDS = {"account", "owner", "type", "amount", "days_remaining", "status", "reason"}
OWNER_FIELDS = {
    "owner",
    "accounts",
    "critical_accounts",
    "attention_accounts",
    "overdue_plan_items",
    "engagement_gaps",
    "expiring_concessions",
    "arr_at_risk",
    "next_action_due",
    "escalation_needed",
}
RISK_ORDER = {"blocked": 0, "critical": 1, "attention": 2, "healthy": 3}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_fixture(root: Path, *, variant: str) -> Path:
    data_dir = root / variant
    data_dir.mkdir()
    segment_policies = [
        {
            "segment": "enterprise",
            "renewal_window_days": 45,
            "min_utilization_pct": 65,
            "executive_arr_threshold": 100000,
            "engagement_gap_days": 14,
        },
        {
            "segment": "midmarket",
            "renewal_window_days": 30,
            "min_utilization_pct": 60,
            "executive_arr_threshold": 75000,
            "engagement_gap_days": 21,
        },
        {
            "segment": "growth",
            "renewal_window_days": 30,
            "min_utilization_pct": 55,
            "executive_arr_threshold": 50000,
            "engagement_gap_days": 21,
        },
        {
            "segment": "startup",
            "renewal_window_days": 21,
            "min_utilization_pct": 50,
            "executive_arr_threshold": 25000,
            "engagement_gap_days": 28,
        },
    ]
    if variant == "hidden-a":
        accounts = [
            {"account_id": "ha-1", "name": "Aster Labs", "owner": "Ada Chen", "segment": "enterprise"},
            {"account_id": "ha-2", "name": "Boreal Energy", "owner": "Ben Cruz", "segment": "midmarket"},
            {"account_id": "ha-3", "name": "Canyon Retail", "owner": "Ada Chen", "segment": "growth"},
        ]
        contracts = {
            "report_date": "2026-09-01",
            "contracts": [
                {"account_id": "ha-1", "status": "active", "renewal_date": "2026-09-12", "arr": 210000},
                {"account_id": "ha-2", "status": "active", "renewal_date": "2026-10-15", "arr": 55000},
                {"account_id": "ha-3", "status": "canceled", "renewal_date": "2026-09-25", "arr": 32000},
            ],
        }
        usage = [
            {"account_id": "ha-1", "active_users": 40, "licensed_seats": 120, "last_login_at": "2026-07-20"},
            {"account_id": "ha-2", "active_users": 72, "licensed_seats": 80, "last_login_at": "2026-08-25"},
            {"account_id": "ha-3", "active_users": 10, "licensed_seats": 0, "last_login_at": "2026-08-31"},
        ]
        tickets = [
            {"account_id": "ha-2", "severity": "critical", "status": "open", "opened_at": "2026-08-30"},
            {"account_id": "ha-1", "severity": "critical", "status": "resolved", "opened_at": "2026-08-20"},
            {"account_id": "ha-3", "severity": "critical", "status": "open", "opened_at": "2026-08-31"},
        ]
        concessions = [
            {"account_id": "ha-1", "type": "discount", "amount": 9000, "expires_on": "2026-09-08", "reason": "adoption recovery"},
            {"account_id": "ha-2", "type": "credit", "amount": 2500, "expires_on": "2026-10-01", "reason": "support incident"},
            {"account_id": "ha-1", "type": "old_credit", "amount": 1000, "expires_on": "2026-08-01", "reason": "expired"},
        ]
        engagements = [
            {"account_id": "ha-1", "channel": "exec-review", "last_contact_at": "2026-08-10", "next_contact_at": "2026-08-30", "status": "open"},
            {"account_id": "ha-2", "channel": "support", "last_contact_at": "2026-08-31", "next_contact_at": "2026-09-04", "status": "open"},
            {"account_id": "ha-3", "channel": "email", "last_contact_at": "2026-08-01", "next_contact_at": "2026-09-05", "status": "open"},
        ]
        renewal_plans = [
            {"account_id": "ha-1", "task_id": "ha-plan-1", "kind": "exec_alignment", "owner": "Ada Chen", "due_date": "2026-08-28", "status": "open"},
            {"account_id": "ha-1", "task_id": "ha-plan-2", "kind": "pricing", "owner": "Ada Chen", "due_date": "2026-09-03", "status": "open"},
            {"account_id": "ha-2", "task_id": "ha-plan-3", "kind": "support", "owner": "Ben Cruz", "due_date": "2026-08-31", "status": "done"},
            {"account_id": "ha-3", "task_id": "ha-plan-4", "kind": "contract", "owner": "Ada Chen", "due_date": "2026-08-25", "status": "blocked"},
        ]
    else:
        accounts = [
            {"account_id": "hb-1", "name": "Delta School", "owner": "Nia Shah", "segment": "growth"},
            {"account_id": "hb-2", "name": "Elm Robotics", "owner": "Nia Shah", "segment": "enterprise"},
            {"account_id": "hb-3", "name": "Fjord Media", "owner": "Omar Reid", "segment": "midmarket"},
            {"account_id": "hb-4", "name": "Grove Studio", "owner": "Pam Yu", "segment": "startup"},
        ]
        contracts = {
            "report_date": "2026-11-10",
            "contracts": [
                {"account_id": "hb-1", "status": "trialing", "renewal_date": "2026-11-20", "arr": 24000},
                {"account_id": "hb-2", "status": "active", "renewal_date": "2026-12-30", "arr": 180000},
                {"account_id": "hb-3", "status": "active", "renewal_date": "2026-11-25", "arr": 76000},
                {"account_id": "hb-4", "status": "active", "renewal_date": "2027-01-05", "arr": 9000},
            ],
        }
        usage = [
            {"account_id": "hb-1", "active_users": 8, "licensed_seats": 30, "last_login_at": "2026-11-09"},
            {"account_id": "hb-2", "active_users": 420, "licensed_seats": 500, "last_login_at": "2026-09-20"},
            {"account_id": "hb-3", "active_users": 70, "licensed_seats": 100, "last_login_at": "2026-11-05"},
            {"account_id": "hb-4", "active_users": 25, "licensed_seats": 30, "last_login_at": "2026-11-04"},
        ]
        tickets = [
            {"account_id": "hb-3", "severity": "critical", "status": "resolved", "opened_at": "2026-11-01"},
            {"account_id": "hb-4", "severity": "low", "status": "open", "opened_at": "2026-11-02"},
        ]
        concessions = [
            {"account_id": "hb-1", "type": "pilot_credit", "amount": 1500, "expires_on": "2026-11-18", "reason": "trial close"},
            {"account_id": "hb-2", "type": "service_credit", "amount": 8000, "expires_on": "2026-12-20", "reason": "stability"},
            {"account_id": "hb-2", "type": "discount", "amount": 5000, "expires_on": "2026-12-01", "reason": "older active duplicate"},
            {"account_id": "hb-3", "type": "expired", "amount": 2000, "expires_on": "2026-10-01", "reason": "expired"},
        ]
        engagements = [
            {"account_id": "hb-1", "channel": "email", "last_contact_at": "2026-11-01", "next_contact_at": "2026-11-09", "status": "open"},
            {"account_id": "hb-2", "channel": "exec-review", "last_contact_at": "2026-10-01", "next_contact_at": "2026-11-20", "status": "open"},
            {"account_id": "hb-3", "channel": "call", "last_contact_at": "2026-11-04", "next_contact_at": "2026-11-18", "status": "open"},
            {"account_id": "hb-4", "channel": "email", "last_contact_at": "2026-11-02", "next_contact_at": "2026-11-12", "status": "open"},
        ]
        renewal_plans = [
            {"account_id": "hb-1", "task_id": "hb-plan-1", "kind": "trial_close", "owner": "Nia Shah", "due_date": "2026-11-08", "status": "open"},
            {"account_id": "hb-2", "task_id": "hb-plan-2", "kind": "exec_check", "owner": "Nia Shah", "due_date": "2026-11-18", "status": "open"},
            {"account_id": "hb-3", "task_id": "hb-plan-3", "kind": "renewal_plan", "owner": "Omar Reid", "due_date": "2026-11-12", "status": "open"},
            {"account_id": "hb-4", "task_id": "hb-plan-4", "kind": "monitor", "owner": "Pam Yu", "due_date": "2026-11-15", "status": "done"},
        ]
    for name, value in [
        ("accounts.json", accounts),
        ("contracts.json", contracts),
        ("usage.json", usage),
        ("tickets.json", tickets),
        ("concessions.json", concessions),
        ("segment_policies.json", segment_policies),
        ("engagements.json", engagements),
        ("renewal_plans.json", renewal_plans),
    ]:
        write_json(data_dir / name, value)
    return data_dir


def load_json(data_dir: Path, name: str) -> object:
    return json.loads((data_dir / name).read_text())


def expected(data_dir: Path) -> dict[str, object]:
    accounts = load_json(data_dir, "accounts.json")
    contracts_doc = load_json(data_dir, "contracts.json")
    usage_rows = load_json(data_dir, "usage.json")
    tickets = load_json(data_dir, "tickets.json")
    concessions = load_json(data_dir, "concessions.json")
    policies = {row["segment"]: row for row in load_json(data_dir, "segment_policies.json")}
    engagements = load_json(data_dir, "engagements.json")
    renewal_plans = load_json(data_dir, "renewal_plans.json")

    report_date = date.fromisoformat(contracts_doc["report_date"])
    contracts = {row["account_id"]: row for row in contracts_doc["contracts"]}
    usage = {row["account_id"]: row for row in usage_rows}
    active_concessions: dict[str, dict[str, object]] = {}
    for concession in concessions:
        expires = date.fromisoformat(concession["expires_on"])
        if expires < report_date:
            continue
        current = active_concessions.get(concession["account_id"])
        if current is None or concession["expires_on"] > current["expires_on"]:
            active_concessions[concession["account_id"]] = concession

    latest_engagement: dict[str, dict[str, object]] = {}
    for engagement in engagements:
        current = latest_engagement.get(engagement["account_id"])
        if current is None or engagement["last_contact_at"] > current["last_contact_at"]:
            latest_engagement[engagement["account_id"]] = engagement

    plans_by_account: dict[str, list[dict[str, object]]] = defaultdict(list)
    for plan in renewal_plans:
        plans_by_account[plan["account_id"]].append(plan)

    open_critical: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket["severity"] == "critical" and ticket["status"] not in {"closed", "resolved"}:
            open_critical[ticket["account_id"]] += 1

    risk_rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = account["account_id"]
        contract = contracts[account_id]
        usage_row = usage[account_id]
        policy = policies[account["segment"]]
        days = (date.fromisoformat(contract["renewal_date"]) - report_date).days
        licensed = int(usage_row["licensed_seats"])
        utilization = 0 if licensed == 0 else int(int(usage_row["active_users"]) * 100 / licensed)
        critical_tickets = int(open_critical.get(account_id, 0))
        concession = active_concessions.get(account_id)
        concession_days: int | str = ""
        concession_expiring = False
        if concession is not None:
            concession_days = (date.fromisoformat(str(concession["expires_on"])) - report_date).days
            concession_expiring = int(concession_days) <= 14

        engagement = latest_engagement[account_id]
        days_since_contact = (report_date - date.fromisoformat(str(engagement["last_contact_at"]))).days
        engagement_gap = (
            days_since_contact > int(policy["engagement_gap_days"])
            or date.fromisoformat(str(engagement["next_contact_at"])) < report_date
        )
        account_plans = plans_by_account.get(account_id, [])
        open_plans = [plan for plan in account_plans if plan["status"] != "done"]
        overdue_plan_items = sum(
            1 for plan in open_plans if date.fromisoformat(str(plan["due_date"])) <= report_date
        )

        contract_active = contract["status"] in {"active", "trialing"}
        stale_usage = (report_date - date.fromisoformat(str(usage_row["last_login_at"]))).days > 30
        high_arr_stale = int(contract["arr"]) >= int(policy["executive_arr_threshold"]) and stale_usage
        renewal_soon = days <= int(policy["renewal_window_days"])
        low_utilization = utilization < int(policy["min_utilization_pct"])

        reasons = []
        if not contract_active:
            reasons.append("contract_not_active")
        if renewal_soon:
            reasons.append("renewal_soon")
        if low_utilization:
            reasons.append("low_seat_utilization")
        if critical_tickets >= 1:
            reasons.append("open_critical_ticket")
        if concession_expiring:
            reasons.append("concession_expiring")
        if high_arr_stale:
            reasons.append("stale_usage")
        if engagement_gap:
            reasons.append("engagement_gap")
        if overdue_plan_items >= 1:
            reasons.append("plan_overdue")

        if not contract_active:
            level = "blocked"
            action = "Restore contract"
        elif critical_tickets >= 1:
            level = "critical"
            action = "Escalate support"
        elif overdue_plan_items >= 1 and renewal_soon:
            level = "critical"
            action = "Clear renewal blockers"
        elif days <= 14 and low_utilization:
            level = "critical"
            action = "Executive renewal review"
        elif renewal_soon:
            level = "attention"
            action = "Schedule renewal plan"
        elif low_utilization:
            level = "attention"
            action = "Drive adoption plan"
        elif concession_expiring:
            level = "attention"
            action = "Review concession"
        elif high_arr_stale:
            level = "attention"
            action = "Verify executive engagement"
        elif engagement_gap:
            level = "attention"
            action = "Re-engage owner"
        else:
            level = "healthy"
            action = "Monitor"

        risk_rows.append(
            {
                "account_id": account_id,
                "account": account["name"],
                "owner": account["owner"],
                "segment": account["segment"],
                "arr": int(contract["arr"]),
                "days_to_renewal": days,
                "seat_utilization_pct": utilization,
                "open_critical_tickets": critical_tickets,
                "concession_days_remaining": concession_days,
                "days_since_contact": days_since_contact,
                "overdue_plan_items": overdue_plan_items,
                "open_plan_items": len(open_plans),
                "engagement_gap": engagement_gap,
                "concession_expiring": concession_expiring,
                "risk_level": level,
                "risk_reasons": ",".join(reasons) if reasons else "none",
                "recommended_action": action,
            }
        )
    risk_rows.sort(key=lambda row: (RISK_ORDER[str(row["risk_level"])], str(row["owner"]), str(row["account"])))

    by_id = {row["account_id"]: row for row in accounts}
    concession_rows: list[dict[str, object]] = []
    for account_id, concession in active_concessions.items():
        account = by_id[account_id]
        days = (date.fromisoformat(str(concession["expires_on"])) - report_date).days
        concession_rows.append(
            {
                "account_id": account_id,
                "account": account["name"],
                "owner": account["owner"],
                "type": concession["type"],
                "amount": int(concession["amount"]),
                "days_remaining": days,
                "status": "expiring" if days <= 14 else "active",
                "reason": concession["reason"],
            }
        )
    concession_rows.sort(key=lambda row: (int(row["days_remaining"]), str(row["owner"]), str(row["account"]), str(row["type"])))

    risk_by_account = {row["account_id"]: row for row in risk_rows}
    open_plans_by_owner: dict[str, list[dict[str, object]]] = defaultdict(list)
    for plan in renewal_plans:
        if plan["status"] != "done":
            open_plans_by_owner[str(plan["owner"])].append(plan)

    owner_rows = []
    for owner in sorted({row["owner"] for row in accounts}):
        owned = [risk_by_account[account["account_id"]] for account in accounts if account["owner"] == owner]
        owner_open_plans = open_plans_by_owner.get(owner, [])
        critical_accounts = sum(row["risk_level"] in {"blocked", "critical"} for row in owned)
        overdue = sum(int(row["overdue_plan_items"]) for row in owned)
        arr_at_risk = sum(int(row["arr"]) for row in owned if row["risk_level"] != "healthy")
        next_action_due = min((str(plan["due_date"]) for plan in owner_open_plans), default="")
        escalation_needed = "yes" if critical_accounts >= 1 or overdue >= 2 else "no"
        owner_rows.append(
            {
                "owner": owner,
                "accounts": len(owned),
                "critical_accounts": critical_accounts,
                "attention_accounts": sum(row["risk_level"] == "attention" for row in owned),
                "overdue_plan_items": overdue,
                "engagement_gaps": sum(bool(row["engagement_gap"]) for row in owned),
                "expiring_concessions": sum(bool(row["concession_expiring"]) for row in owned),
                "arr_at_risk": arr_at_risk,
                "next_action_due": next_action_due,
                "escalation_needed": escalation_needed,
            }
        )
    owner_rows.sort(
        key=lambda row: (
            0 if row["escalation_needed"] == "yes" else 1,
            -int(row["arr_at_risk"]),
            str(row["owner"]),
        )
    )

    return {
        "risk_rows": risk_rows,
        "risk_metrics": {
            "accounts": len(accounts),
            "critical": sum(row["risk_level"] in {"blocked", "critical"} for row in risk_rows),
            "attention": sum(row["risk_level"] == "attention" for row in risk_rows),
            "concessions-expiring": sum(bool(row["concession_expiring"]) for row in risk_rows),
            "overdue-plans": sum(int(row["overdue_plan_items"]) for row in risk_rows),
            "engagement-gaps": sum(bool(row["engagement_gap"]) for row in risk_rows),
        },
        "concession_rows": concession_rows,
        "concession_metrics": {
            "active-concessions": len(concession_rows),
            "expiring-concessions": sum(row["status"] == "expiring" for row in concession_rows),
            "total-concession-amount": sum(int(row["amount"]) for row in concession_rows),
        },
        "owner_rows": owner_rows,
        "owner_metrics": {
            "owners": len(owner_rows),
            "owners-with-escalations": sum(row["escalation_needed"] == "yes" for row in owner_rows),
            "overdue-plan-items": sum(int(row["overdue_plan_items"]) for row in owner_rows),
            "arr-at-risk": sum(int(row["arr_at_risk"]) for row in owner_rows),
        },
    }


class ContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.main_screens: list[str] = []
        self.h1_texts: list[str] = []
        self.metrics: dict[str, str] = {}
        self.tables: dict[str, list[dict[str, object]]] = defaultdict(list)
        self._metric: str | None = None
        self._metric_text: list[str] = []
        self._h1 = False
        self._h1_text: list[str] = []
        self._table: str | None = None
        self._row: dict[str, object] | None = None
        self._field: str | None = None
        self._field_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "main" and "data-screen" in attr:
            self.main_screens.append(attr["data-screen"])
        if tag == "h1":
            self._h1 = True
            self._h1_text = []
        if "data-metric" in attr:
            self._metric = attr["data-metric"]
            self._metric_text = []
        if tag == "table" and "data-table" in attr:
            self._table = attr["data-table"]
        if tag == "tr" and self._table:
            if "data-account-id" in attr:
                self._row = {"row_key": attr["data-account-id"], "fields": {}}
            elif "data-owner" in attr:
                self._row = {"row_key": attr["data-owner"], "fields": {}}
        if tag == "td" and self._row is not None and "data-field" in attr:
            self._field = attr["data-field"]
            self._field_text = []

    def handle_data(self, data: str) -> None:
        if self._metric is not None:
            self._metric_text.append(data)
        if self._h1:
            self._h1_text.append(data)
        if self._field is not None:
            self._field_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._h1:
            self.h1_texts.append("".join(self._h1_text).strip())
            self._h1 = False
        if self._metric is not None and tag in {"span", "div", "section", "strong"}:
            self.metrics[self._metric] = "".join(self._metric_text).strip()
            self._metric = None
        if tag == "td" and self._row is not None and self._field is not None:
            self._row["fields"][self._field] = "".join(self._field_text).strip()
            self._field = None
        if tag == "tr" and self._table and self._row is not None:
            self.tables[self._table].append(self._row)
            self._row = None
        if tag == "table":
            self._table = None


def parse(html: str) -> ContractParser:
    parser = ContractParser()
    parser.feed(html)
    return parser


def render(route: str, data_dir: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.html"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "workspace_app.cli",
                "--route",
                route,
                "--data-dir",
                str(data_dir),
                "--output",
                str(out),
            ],
            check=True,
            cwd=app,
        )
        return out.read_text()


def assert_metrics(tc: unittest.TestCase, parser: ContractParser, expected_metrics: dict[str, object]) -> None:
    tc.assertEqual(parser.metrics, {key: str(value) for key, value in expected_metrics.items()})


def assert_table_rows(
    tc: unittest.TestCase,
    rows: list[dict[str, object]],
    expected_rows: list[dict[str, object]],
    *,
    key: str,
    fields: set[str],
) -> None:
    tc.assertEqual(len(rows), len(expected_rows))
    tc.assertEqual([row["row_key"] for row in rows], [row[key] for row in expected_rows])
    actual = {row["row_key"]: row["fields"] for row in rows}
    for expected_row in expected_rows:
        row_fields = actual[expected_row[key]]
        tc.assertEqual(set(row_fields), fields)
        for field in fields:
            tc.assertEqual(row_fields[field], str(expected_row[field]), (expected_row[key], field))


def assert_risk(tc: unittest.TestCase, data_dir: Path) -> None:
    exp = expected(data_dir)
    html = render("/renewals/risk", data_dir)
    parser = parse(html)
    tc.assertIn("renewal-risk", parser.main_screens)
    tc.assertIn("Renewal Risk", parser.h1_texts)
    tc.assertIn('href="/renewals/risk"', html)
    tc.assertIn(">Renewals</a>", html)
    assert_metrics(tc, parser, exp["risk_metrics"])
    assert_table_rows(
        tc,
        parser.tables.get("renewal-risk", []),
        exp["risk_rows"],
        key="account_id",
        fields=RISK_FIELDS,
    )


def assert_concessions(tc: unittest.TestCase, data_dir: Path) -> None:
    exp = expected(data_dir)
    html = render("/renewals/concessions", data_dir)
    parser = parse(html)
    tc.assertIn("renewal-concessions", parser.main_screens)
    tc.assertIn("Renewal Concessions", parser.h1_texts)
    assert_metrics(tc, parser, exp["concession_metrics"])
    assert_table_rows(
        tc,
        parser.tables.get("renewal-concessions", []),
        exp["concession_rows"],
        key="account_id",
        fields=CONCESSION_FIELDS,
    )


def assert_owner_queue(tc: unittest.TestCase, data_dir: Path) -> None:
    exp = expected(data_dir)
    html = render("/renewals/owner-queue", data_dir)
    parser = parse(html)
    tc.assertIn("renewal-owner-queue", parser.main_screens)
    tc.assertIn("Renewal Owner Queue", parser.h1_texts)
    assert_metrics(tc, parser, exp["owner_metrics"])
    assert_table_rows(
        tc,
        parser.tables.get("renewal-owner-queue", []),
        exp["owner_rows"],
        key="owner",
        fields=OWNER_FIELDS,
    )


class RenewalVerifier(unittest.TestCase):
    def test_source_structure_and_unittest_regression(self) -> None:
        for path in [
            app / "workspace_app" / "screens" / "renewal_risk.py",
            app / "workspace_app" / "screens" / "renewal_concessions.py",
            app / "workspace_app" / "screens" / "renewal_owner_queue.py",
            app / "workspace_app" / "selectors" / "renewals.py",
            app / "workspace_app" / "components" / "renewal_badges.py",
        ]:
            self.assertTrue(path.exists(), path)
        routing = (app / "workspace_app" / "routing.py").read_text()
        self.assertIn("/renewals/risk", routing)
        self.assertIn("/renewals/concessions", routing)
        self.assertIn("/renewals/owner-queue", routing)
        nav = (app / "workspace_app" / "nav.py").read_text()
        self.assertIn("Renewals", nav)
        self.assertIn("/renewals/risk", nav)
        test_files = list((app / "tests").glob("test*.py"))
        self.assertTrue(test_files)
        text = "\n".join(path.read_text() for path in test_files)
        self.assertIn("/renewals/risk", text)
        self.assertIn("/renewals/concessions", text)
        self.assertIn("/renewals/owner-queue", text)
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=app, check=True)

    def test_existing_routes_still_render_and_nav_includes_new_item(self) -> None:
        for route, screen in [
            ("/", "home"),
            ("/accounts", "accounts"),
            ("/support", "support"),
            ("/billing", "billing"),
            ("/reports", "reports"),
        ]:
            html = render(route, app / "fixtures" / "visible")
            self.assertIn(f'data-screen="{screen}"', html)
            self.assertIn('href="/renewals/risk"', html)
            self.assertIn(">Renewals</a>", html)

    def test_visible_fixture_exact(self) -> None:
        data = app / "fixtures" / "visible"
        assert_risk(self, data)
        assert_concessions(self, data)
        assert_owner_queue(self, data)

    def test_hidden_fixtures_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for variant in ["hidden-a", "hidden-b"]:
                with self.subTest(variant=variant):
                    data = write_fixture(root, variant=variant)
                    assert_risk(self, data)
                    assert_concessions(self, data)
                    assert_owner_queue(self, data)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(RenewalVerifier)
result = unittest.TextTestRunner(verbosity=1).run(suite)
Path(os.environ.get("LOG_DIR", "/logs/verifier"), "reward.txt").write_text(
    "1" if result.wasSuccessful() else "0"
)
if not result.wasSuccessful():
    sys.exit(1)
PY

status=$?
cat "$LOG_DIR/reward.txt" 2>/dev/null || echo 0
exit "$status"

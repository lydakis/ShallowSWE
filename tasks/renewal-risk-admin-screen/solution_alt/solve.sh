#!/usr/bin/env bash
set -euo pipefail

cat > workspace_app/components/renewal_badges.py <<'PY'
from __future__ import annotations

from html import escape


def metric_span(key: str, value: object) -> str:
    return '<span data-metric="%s">%s</span>' % (escape(key), escape(str(value)))


def table_cell(field: str, value: object) -> str:
    return '<td data-field="%s">%s</td>' % (escape(field), escape(str(value)))
PY

cat > workspace_app/selectors/renewals.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from workspace_app.data import load_json


RISK_ORDER = {"blocked": 0, "critical": 1, "attention": 2, "healthy": 3}


def _load(data_dir: str | Path) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    return (
        load_json(data_dir, "accounts.json"),
        load_json(data_dir, "contracts.json"),
        load_json(data_dir, "usage.json"),
        load_json(data_dir, "tickets.json"),
        load_json(data_dir, "concessions.json"),
        load_json(data_dir, "segment_policies.json"),
        load_json(data_dir, "engagements.json"),
        load_json(data_dir, "renewal_plans.json"),
    )


def _active_concessions(
    concessions: list[dict[str, Any]],
    report_date: date,
) -> dict[str, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    for concession in concessions:
        expires = date.fromisoformat(str(concession["expires_on"]))
        if expires < report_date:
            continue
        account_id = str(concession["account_id"])
        current = active.get(account_id)
        if current is None or str(concession["expires_on"]) > str(current["expires_on"]):
            active[account_id] = concession
    return active


def renewal_data(data_dir: str | Path) -> dict[str, object]:
    (
        accounts,
        contracts_doc,
        usage_rows,
        tickets,
        concessions,
        segment_policies,
        engagements,
        renewal_plans,
    ) = _load(data_dir)
    report_date = date.fromisoformat(str(contracts_doc["report_date"]))
    contracts = {str(row["account_id"]): row for row in contracts_doc["contracts"]}
    usage = {str(row["account_id"]): row for row in usage_rows}
    policies = {str(row["segment"]): row for row in segment_policies}
    active_concessions = _active_concessions(concessions, report_date)

    latest_engagement: dict[str, dict[str, Any]] = {}
    for engagement in engagements:
        account_id = str(engagement["account_id"])
        current = latest_engagement.get(account_id)
        if current is None or str(engagement["last_contact_at"]) > str(current["last_contact_at"]):
            latest_engagement[account_id] = engagement

    plans_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    open_plans_by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for plan in renewal_plans:
        account_id = str(plan["account_id"])
        plans_by_account[account_id].append(plan)
        if plan["status"] != "done":
            open_plans_by_owner[str(plan["owner"])].append(plan)

    open_critical: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket["severity"] == "critical" and ticket["status"] not in {"closed", "resolved"}:
            open_critical[str(ticket["account_id"])] += 1

    risk_rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = str(account["account_id"])
        contract = contracts[account_id]
        usage_row = usage[account_id]
        policy = policies[str(account["segment"])]
        days_to_renewal = (
            date.fromisoformat(str(contract["renewal_date"])) - report_date
        ).days
        licensed = int(usage_row["licensed_seats"])
        utilization = 0 if licensed == 0 else int(int(usage_row["active_users"]) * 100 / licensed)
        critical_tickets = open_critical.get(account_id, 0)

        concession = active_concessions.get(account_id)
        concession_days: int | str = ""
        concession_expiring = False
        if concession is not None:
            concession_days = (
                date.fromisoformat(str(concession["expires_on"])) - report_date
            ).days
            concession_expiring = int(concession_days) <= 14

        engagement = latest_engagement[account_id]
        days_since_contact = (
            report_date - date.fromisoformat(str(engagement["last_contact_at"]))
        ).days
        engagement_gap = (
            days_since_contact > int(policy["engagement_gap_days"])
            or date.fromisoformat(str(engagement["next_contact_at"])) < report_date
        )

        open_plans = [plan for plan in plans_by_account.get(account_id, []) if plan["status"] != "done"]
        overdue_plan_items = sum(
            1
            for plan in open_plans
            if date.fromisoformat(str(plan["due_date"])) <= report_date
        )

        contract_active = contract["status"] in {"active", "trialing"}
        stale_usage = (report_date - date.fromisoformat(str(usage_row["last_login_at"]))).days > 30
        renewal_soon = days_to_renewal <= int(policy["renewal_window_days"])
        low_utilization = utilization < int(policy["min_utilization_pct"])
        high_arr_stale = int(contract["arr"]) >= int(policy["executive_arr_threshold"]) and stale_usage

        reasons: list[str] = []
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
            risk_level = "blocked"
            recommended_action = "Restore contract"
        elif critical_tickets >= 1:
            risk_level = "critical"
            recommended_action = "Escalate support"
        elif overdue_plan_items >= 1 and renewal_soon:
            risk_level = "critical"
            recommended_action = "Clear renewal blockers"
        elif days_to_renewal <= 14 and low_utilization:
            risk_level = "critical"
            recommended_action = "Executive renewal review"
        elif renewal_soon:
            risk_level = "attention"
            recommended_action = "Schedule renewal plan"
        elif low_utilization:
            risk_level = "attention"
            recommended_action = "Drive adoption plan"
        elif concession_expiring:
            risk_level = "attention"
            recommended_action = "Review concession"
        elif high_arr_stale:
            risk_level = "attention"
            recommended_action = "Verify executive engagement"
        elif engagement_gap:
            risk_level = "attention"
            recommended_action = "Re-engage owner"
        else:
            risk_level = "healthy"
            recommended_action = "Monitor"

        risk_rows.append(
            {
                "account_id": account_id,
                "account": account["name"],
                "owner": account["owner"],
                "segment": account["segment"],
                "arr": int(contract["arr"]),
                "days_to_renewal": days_to_renewal,
                "seat_utilization_pct": utilization,
                "open_critical_tickets": critical_tickets,
                "concession_days_remaining": concession_days,
                "days_since_contact": days_since_contact,
                "overdue_plan_items": overdue_plan_items,
                "open_plan_items": len(open_plans),
                "engagement_gap": engagement_gap,
                "concession_expiring": concession_expiring,
                "risk_level": risk_level,
                "risk_reasons": ",".join(reasons) if reasons else "none",
                "recommended_action": recommended_action,
            }
        )

    risk_rows.sort(key=lambda row: (RISK_ORDER[str(row["risk_level"])], str(row["owner"]), str(row["account"])))

    account_by_id = {str(row["account_id"]): row for row in accounts}
    concession_rows: list[dict[str, object]] = []
    for account_id, concession in active_concessions.items():
        account = account_by_id[account_id]
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

    risk_by_account = {str(row["account_id"]): row for row in risk_rows}
    owner_rows: list[dict[str, object]] = []
    for owner in sorted({str(row["owner"]) for row in accounts}):
        owned = [
            risk_by_account[str(account["account_id"])]
            for account in accounts
            if str(account["owner"]) == owner
        ]
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


def risk_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    data = renewal_data(data_dir)
    return data["risk_rows"], data["risk_metrics"]


def concession_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    data = renewal_data(data_dir)
    return data["concession_rows"], data["concession_metrics"]


def owner_queue_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    data = renewal_data(data_dir)
    return data["owner_rows"], data["owner_metrics"]
PY

cat > workspace_app/screens/renewal_risk.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.components.renewal_badges import metric_span, table_cell
from workspace_app.layout import render_layout
from workspace_app.selectors.renewals import risk_rows


METRICS = ["accounts", "critical", "attention", "concessions-expiring", "overdue-plans", "engagement-gaps"]
FIELDS = [
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
]


def render(data_dir: Path) -> str:
    rows, metrics = risk_rows(data_dir)
    metric_html = "".join(metric_span(key, metrics[key]) for key in METRICS)
    headers = "".join("<th>%s</th>" % escape(field.replace("_", " ").title()) for field in FIELDS)
    body_rows = []
    for row in rows:
        cells = "".join(table_cell(field, row[field]) for field in FIELDS)
        body_rows.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    table = '<table data-table="renewal-risk"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body_rows),
    )
    body = '<h1>Renewal Risk</h1><section class="metrics">%s</section>%s' % (metric_html, table)
    return render_layout("Renewal Risk", "/renewals/risk", body, data_screen="renewal-risk")
PY

cat > workspace_app/screens/renewal_concessions.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.components.renewal_badges import metric_span, table_cell
from workspace_app.layout import render_layout
from workspace_app.selectors.renewals import concession_rows


METRICS = ["active-concessions", "expiring-concessions", "total-concession-amount"]
FIELDS = ["account", "owner", "type", "amount", "days_remaining", "status", "reason"]


def render(data_dir: Path) -> str:
    rows, metrics = concession_rows(data_dir)
    metric_html = "".join(metric_span(key, metrics[key]) for key in METRICS)
    headers = "".join("<th>%s</th>" % escape(field.replace("_", " ").title()) for field in FIELDS)
    body_rows = []
    for row in rows:
        cells = "".join(table_cell(field, row[field]) for field in FIELDS)
        body_rows.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    table = '<table data-table="renewal-concessions"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body_rows),
    )
    body = '<h1>Renewal Concessions</h1><section class="metrics">%s</section>%s' % (metric_html, table)
    return render_layout("Renewal Concessions", "/renewals/concessions", body, data_screen="renewal-concessions")
PY

cat > workspace_app/screens/renewal_owner_queue.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.components.renewal_badges import metric_span, table_cell
from workspace_app.layout import render_layout
from workspace_app.selectors.renewals import owner_queue_rows


METRICS = ["owners", "owners-with-escalations", "overdue-plan-items", "arr-at-risk"]
FIELDS = [
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
]


def render(data_dir: Path) -> str:
    rows, metrics = owner_queue_rows(data_dir)
    metric_html = "".join(metric_span(key, metrics[key]) for key in METRICS)
    headers = "".join("<th>%s</th>" % escape(field.replace("_", " ").title()) for field in FIELDS)
    body_rows = []
    for row in rows:
        cells = "".join(table_cell(field, row[field]) for field in FIELDS)
        body_rows.append('<tr data-owner="%s">%s</tr>' % (escape(str(row["owner"])), cells))
    table = '<table data-table="renewal-owner-queue"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body_rows),
    )
    body = '<h1>Renewal Owner Queue</h1><section class="metrics">%s</section>%s' % (metric_html, table)
    return render_layout("Renewal Owner Queue", "/renewals/owner-queue", body, data_screen="renewal-owner-queue")
PY

cat > workspace_app/nav.py <<'PY'
NAV_ITEMS = [
    {"label": "Home", "href": "/"},
    {"label": "Accounts", "href": "/accounts"},
    {"label": "Support", "href": "/support"},
    {"label": "Billing", "href": "/billing"},
    {"label": "Reports", "href": "/reports"},
    {"label": "Renewals", "href": "/renewals/risk"},
]
PY

cat > workspace_app/routing.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .screens import (
    accounts,
    billing,
    home,
    renewal_concessions,
    renewal_owner_queue,
    renewal_risk,
    reports,
    support,
)

RenderFn = Callable[[Path], str]

ROUTES: dict[str, RenderFn] = {
    "/": home.render,
    "/accounts": accounts.render,
    "/support": support.render,
    "/billing": billing.render,
    "/reports": reports.render,
    "/renewals/risk": renewal_risk.render,
    "/renewals/concessions": renewal_concessions.render,
    "/renewals/owner-queue": renewal_owner_queue.render,
}


def route_names() -> list[str]:
    return sorted(ROUTES)


def render_route(route: str, data_dir: str | Path) -> str:
    if route not in ROUTES:
        known = ", ".join(route_names())
        raise SystemExit(f"Unknown route {route!r}. Known routes: {known}")
    return ROUTES[route](Path(data_dir))
PY

cat > tests/test_renewals.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DATA_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "visible"


def render(route: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "out.html"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "workspace_app.cli",
                "--route",
                route,
                "--data-dir",
                str(DATA_DIR),
                "--output",
                str(output),
            ],
            check=True,
        )
        return output.read_text()


class RenewalTests(unittest.TestCase):
    def test_risk_route_renders(self) -> None:
        html = render("/renewals/risk")
        self.assertIn('data-screen="renewal-risk"', html)
        self.assertIn("<h1>Renewal Risk</h1>", html)
        self.assertIn('href="/renewals/risk">Renewals</a>', html)
        for key in ["accounts", "critical", "attention", "concessions-expiring", "overdue-plans", "engagement-gaps"]:
            self.assertIn(f'data-metric="{key}"', html)
        self.assertIn('data-table="renewal-risk"', html)

    def test_concessions_route_renders(self) -> None:
        html = render("/renewals/concessions")
        self.assertIn('data-screen="renewal-concessions"', html)
        self.assertIn("<h1>Renewal Concessions</h1>", html)
        for key in ["active-concessions", "expiring-concessions", "total-concession-amount"]:
            self.assertIn(f'data-metric="{key}"', html)
        self.assertIn('data-table="renewal-concessions"', html)

    def test_owner_queue_route_renders(self) -> None:
        html = render("/renewals/owner-queue")
        self.assertIn('data-screen="renewal-owner-queue"', html)
        self.assertIn("<h1>Renewal Owner Queue</h1>", html)
        for key in ["owners", "owners-with-escalations", "overdue-plan-items", "arr-at-risk"]:
            self.assertIn(f'data-metric="{key}"', html)
        self.assertIn('data-table="renewal-owner-queue"', html)


if __name__ == "__main__":
    unittest.main()
PY

python3 -m unittest discover -s tests

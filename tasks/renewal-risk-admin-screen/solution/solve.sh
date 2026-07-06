#!/usr/bin/env bash
set -euo pipefail

cat > workspace_app/selectors/renewals.py <<'PY'
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from workspace_app.data import load_json


RISK_ORDER = {"blocked": 0, "critical": 1, "attention": 2, "healthy": 3}


def _load(data_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    accounts = load_json(data_dir, "accounts.json")
    contracts = load_json(data_dir, "contracts.json")
    usage = load_json(data_dir, "usage.json")
    tickets = load_json(data_dir, "tickets.json")
    concessions = load_json(data_dir, "concessions.json")
    return accounts, contracts, usage, tickets, concessions


def _active_concessions(concessions: list[dict[str, Any]], report_date: date) -> dict[str, dict[str, Any]]:
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


def renewal_data(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int], list[dict[str, object]], dict[str, int]]:
    accounts, contracts_doc, usage_rows, tickets, concessions = _load(data_dir)
    report_date = date.fromisoformat(str(contracts_doc["report_date"]))
    contracts = {str(row["account_id"]): row for row in contracts_doc["contracts"]}
    usage = {str(row["account_id"]): row for row in usage_rows}
    active_concessions = _active_concessions(concessions, report_date)

    open_critical: dict[str, int] = {}
    for ticket in tickets:
        if ticket["severity"] == "critical" and ticket["status"] not in {"closed", "resolved"}:
            account_id = str(ticket["account_id"])
            open_critical[account_id] = open_critical.get(account_id, 0) + 1

    risk_rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = str(account["account_id"])
        contract = contracts[account_id]
        usage_row = usage[account_id]
        days = (date.fromisoformat(str(contract["renewal_date"])) - report_date).days
        licensed = int(usage_row["licensed_seats"])
        utilization = 0 if licensed == 0 else int(int(usage_row["active_users"]) * 100 / licensed)
        critical_tickets = open_critical.get(account_id, 0)
        concession = active_concessions.get(account_id)
        concession_days: int | str = ""
        concession_expiring = False
        if concession is not None:
            concession_days = (date.fromisoformat(str(concession["expires_on"])) - report_date).days
            concession_expiring = int(concession_days) <= 14

        contract_active = contract["status"] in {"active", "trialing"}
        stale_usage = (report_date - date.fromisoformat(str(usage_row["last_login_at"]))).days > 30
        high_arr_stale = int(contract["arr"]) >= 100000 and stale_usage

        reasons: list[str] = []
        if not contract_active:
            reasons.append("contract_not_active")
        if days <= 30:
            reasons.append("renewal_soon")
        if utilization < 60:
            reasons.append("low_seat_utilization")
        if critical_tickets >= 1:
            reasons.append("open_critical_ticket")
        if concession_expiring:
            reasons.append("concession_expiring")
        if high_arr_stale:
            reasons.append("stale_usage")

        if not contract_active:
            risk_level = "blocked"
            action = "Restore contract"
        elif critical_tickets >= 1:
            risk_level = "critical"
            action = "Escalate support"
        elif days <= 14 and utilization < 50:
            risk_level = "critical"
            action = "Executive renewal review"
        elif days <= 30:
            risk_level = "attention"
            action = "Schedule renewal plan"
        elif utilization < 60:
            risk_level = "attention"
            action = "Drive adoption plan"
        elif concession_expiring:
            risk_level = "attention"
            action = "Review concession"
        elif high_arr_stale:
            risk_level = "attention"
            action = "Verify executive engagement"
        else:
            risk_level = "healthy"
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
                "risk_level": risk_level,
                "risk_reasons": ",".join(reasons) if reasons else "none",
                "recommended_action": action,
            }
        )

    risk_rows.sort(key=lambda row: (RISK_ORDER[str(row["risk_level"])], str(row["owner"]), str(row["account"])))
    risk_metrics = {
        "accounts": len(accounts),
        "critical": sum(row["risk_level"] in {"blocked", "critical"} for row in risk_rows),
        "attention": sum(row["risk_level"] == "attention" for row in risk_rows),
        "concessions-expiring": sum(
            row["concession_days_remaining"] != "" and int(row["concession_days_remaining"]) <= 14
            for row in risk_rows
        ),
    }

    by_id = {str(row["account_id"]): row for row in accounts}
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
    concession_metrics = {
        "active-concessions": len(concession_rows),
        "expiring-concessions": sum(row["status"] == "expiring" for row in concession_rows),
        "total-concession-amount": sum(int(row["amount"]) for row in concession_rows),
    }
    return risk_rows, risk_metrics, concession_rows, concession_metrics


def risk_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    rows, metrics, _, _ = renewal_data(data_dir)
    return rows, metrics


def concession_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    _, _, rows, metrics = renewal_data(data_dir)
    return rows, metrics
PY

cat > workspace_app/screens/renewal_risk.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.renewals import risk_rows


METRICS = ["accounts", "critical", "attention", "concessions-expiring"]
FIELDS = [
    "account",
    "owner",
    "segment",
    "arr",
    "days_to_renewal",
    "seat_utilization_pct",
    "open_critical_tickets",
    "concession_days_remaining",
    "risk_level",
    "risk_reasons",
    "recommended_action",
]


def _metrics(metrics: dict[str, int]) -> str:
    return '<section class="metrics">%s</section>' % "".join(
        '<span data-metric="%s">%s</span>' % (escape(key), escape(str(metrics[key])))
        for key in METRICS
    )


def _table(rows: list[dict[str, object]]) -> str:
    headers = "".join("<th>%s</th>" % escape(field.replace("_", " ").title()) for field in FIELDS)
    body_rows = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field in FIELDS
        )
        body_rows.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    return '<table data-table="renewal-risk"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body_rows),
    )


def render(data_dir: Path) -> str:
    rows, metrics = risk_rows(data_dir)
    body = "<h1>Renewal Risk</h1>%s%s" % (_metrics(metrics), _table(rows))
    return render_layout("Renewal Risk", "/renewals/risk", body, data_screen="renewal-risk")
PY

cat > workspace_app/screens/renewal_concessions.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.renewals import concession_rows


METRICS = ["active-concessions", "expiring-concessions", "total-concession-amount"]
FIELDS = ["account", "owner", "type", "amount", "days_remaining", "status", "reason"]


def render(data_dir: Path) -> str:
    rows, metrics = concession_rows(data_dir)
    metric_html = "".join(
        '<span data-metric="%s">%s</span>' % (escape(key), escape(str(metrics[key])))
        for key in METRICS
    )
    headers = "".join("<th>%s</th>" % escape(field.replace("_", " ").title()) for field in FIELDS)
    body_rows = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field in FIELDS
        )
        body_rows.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    table = '<table data-table="renewal-concessions"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body_rows),
    )
    body = '<h1>Renewal Concessions</h1><section class="metrics">%s</section>%s' % (metric_html, table)
    return render_layout("Renewal Concessions", "/renewals/concessions", body, data_screen="renewal-concessions")
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

from .screens import accounts, billing, home, renewal_concessions, renewal_risk, reports, support

RenderFn = Callable[[Path], str]

ROUTES: dict[str, RenderFn] = {
    "/": home.render,
    "/accounts": accounts.render,
    "/support": support.render,
    "/billing": billing.render,
    "/reports": reports.render,
    "/renewals/risk": renewal_risk.render,
    "/renewals/concessions": renewal_concessions.render,
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
import re
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
        for key in ["accounts", "critical", "attention", "concessions-expiring"]:
            self.assertRegex(html, rf'data-metric="{key}">[0-9]+<')
        self.assertIn('data-table="renewal-risk"', html)
        self.assertEqual(len(re.findall(r'<tr data-account-id="', html)), 4)

    def test_concessions_route_renders(self) -> None:
        html = render("/renewals/concessions")
        self.assertIn('data-screen="renewal-concessions"', html)
        self.assertIn("<h1>Renewal Concessions</h1>", html)
        for key in ["active-concessions", "expiring-concessions", "total-concession-amount"]:
            self.assertRegex(html, rf'data-metric="{key}">[0-9]+<')
        self.assertIn('data-table="renewal-concessions"', html)


if __name__ == "__main__":
    unittest.main()
PY

python -m unittest discover -s tests

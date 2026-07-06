#!/usr/bin/env bash
set -euo pipefail

cat > workspace_app/selectors/customer_health.py <<'PY'
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from workspace_app.data import load_json


IMPORTANT_SEVERITIES = {"major", "critical"}


def _index(rows: list[dict[str, object]], key: str) -> dict[str, dict[str, object]]:
    return {str(row[key]): row for row in rows}


def _band(score: int) -> str:
    return "high" if score >= 70 else "medium" if score >= 40 else "low"


def _recommend(incidents: int, days: int, band: str, open_tickets: int, usage_delta: int) -> str:
    if incidents > 0:
        return "Escalate incident response"
    if days <= 30 and band == "high":
        return "Schedule renewal save plan"
    if open_tickets >= 4:
        return "Clear support queue"
    if usage_delta < 0:
        return "Review adoption drop"
    return "Monitor"


def customer_health_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    accounts = load_json(data_dir, "accounts.json")
    tickets = load_json(data_dir, "tickets.json")
    incidents = load_json(data_dir, "incidents.json")
    usage_by_account = _index(load_json(data_dir, "usage.json"), "account_id")
    renewal_doc = load_json(data_dir, "renewals.json")
    report_date = date.fromisoformat(renewal_doc["report_date"])
    renewals = _index(renewal_doc["renewals"], "account_id")

    open_ticket_counts = Counter(
        str(ticket["account_id"]) for ticket in tickets if ticket.get("status") == "open"
    )
    open_incident_counts = Counter(
        str(incident["account_id"])
        for incident in incidents
        if incident.get("status") == "open" and incident.get("severity") in IMPORTANT_SEVERITIES
    )

    rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = str(account["account_id"])
        usage = usage_by_account[account_id]
        previous = int(usage["previous_period_events"])
        current = int(usage["current_period_events"])
        usage_delta = current - previous
        days = (date.fromisoformat(renewals[account_id]["renewal_date"]) - report_date).days
        ticket_count = open_ticket_counts[account_id]
        incident_count = open_incident_counts[account_id]
        score = (
            (40 if days <= 30 else 0)
            + (25 if incident_count else 0)
            + min(30, ticket_count * 6)
            + (20 if usage_delta < 0 else 0)
            - (10 if account["plan"] == "enterprise" and usage_delta > 0 else 0)
        )
        score = max(0, min(100, score))
        band = _band(score)
        rows.append(
            {
                "account_id": account_id,
                "name": account["name"],
                "owner": account["owner"],
                "plan": account["plan"],
                "risk_score": score,
                "risk_band": band,
                "open_ticket_count": ticket_count,
                "open_incident_count": incident_count,
                "days_until_renewal": days,
                "recommended_action": _recommend(
                    incident_count,
                    days,
                    band,
                    ticket_count,
                    usage_delta,
                ),
            }
        )
    rows.sort(key=lambda row: (-row["risk_score"], row["days_until_renewal"], row["name"]))
    metrics = {
        "accounts": len(rows),
        "high-risk": sum(1 for row in rows if row["risk_band"] == "high"),
        "open-tickets": sum(row["open_ticket_count"] for row in rows),
        "renewals-30d": sum(1 for row in rows if 0 <= row["days_until_renewal"] <= 30),
    }
    return rows, metrics
PY

cat > workspace_app/screens/customer_health.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.customer_health import customer_health_rows


COLUMNS = [
    "name",
    "owner",
    "plan",
    "risk_score",
    "risk_band",
    "open_ticket_count",
    "open_incident_count",
    "days_until_renewal",
    "recommended_action",
]


def _metric(name: str, value: object) -> str:
    return '<div class="metric" data-metric="%s">%s</div>' % (escape(name), escape(str(value)))


def _row(row: dict[str, object]) -> str:
    cells = "".join(
        '<td data-field="%s">%s</td>' % (escape(column), escape(str(row[column])))
        for column in COLUMNS
    )
    return '<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells)


def render(data_dir: Path) -> str:
    rows, metrics = customer_health_rows(data_dir)
    metric_html = "".join(_metric(key, metrics[key]) for key in ["accounts", "high-risk", "open-tickets", "renewals-30d"])
    headers = "".join("<th>%s</th>" % escape(column.replace("_", " ").title()) for column in COLUMNS)
    table = '<table data-table="customer-health-risks"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(_row(row) for row in rows),
    )
    body = '<h1>Customer Health</h1><section class="health-metrics">%s</section>%s' % (metric_html, table)
    return render_layout("Customer Health", "/customer-health", body, data_screen="customer-health")
PY

python - <<'PY'
from pathlib import Path

routing = Path("workspace_app/routing.py")
source = routing.read_text()
if "customer_health" not in source:
    source = source.replace(
        "from .screens import accounts, billing, home, reports, support",
        "from .screens import accounts, billing, customer_health, home, reports, support",
    )
if '"/customer-health"' not in source:
    source = source.replace('    "/reports": reports.render,\n}', '    "/reports": reports.render,\n    "/customer-health": customer_health.render,\n}')
routing.write_text(source)

nav = Path("workspace_app/nav.py")
source = nav.read_text()
if "/customer-health" not in source:
    source = source.replace(
        ']\n',
        '    {"label": "Customer Health", "href": "/customer-health"},\n]\n',
    )
nav.write_text(source)
PY

cat > tests/test_customer_health.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CustomerHealthScreenTests(unittest.TestCase):
    def test_route_contract_and_visible_customer_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.html"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "workspace_app.cli",
                    "--route",
                    "/customer-health",
                    "--data-dir",
                    "/app/fixtures/visible",
                    "--output",
                    str(output),
                ],
                check=True,
            )
            html = output.read_text()
        self.assertIn('<main data-screen="customer-health">', html)
        self.assertIn("<h1>Customer Health</h1>", html)
        self.assertIn('data-table="customer-health-risks"', html)
        self.assertIn('data-account-id="acct-200"', html)
        self.assertIn("Clear support queue", html)


if __name__ == "__main__":
    unittest.main()
PY

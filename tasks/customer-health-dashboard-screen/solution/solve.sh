#!/usr/bin/env bash
set -euo pipefail

cat > workspace_app/selectors/customer_health.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from workspace_app.data import load_json


def _open_ticket_counts(tickets: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket.get("status") == "open":
            counts[str(ticket.get("account_id"))] += 1
    return counts


def _open_incident_counts(incidents: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for incident in incidents:
        if incident.get("status") == "open" and incident.get("severity") in {"major", "critical"}:
            counts[str(incident.get("account_id"))] += 1
    return counts


def _risk_band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _action(*, incident_count: int, days: int, band: str, tickets: int, usage_down: bool) -> str:
    if incident_count:
        return "Escalate incident response"
    if days <= 30 and band == "high":
        return "Schedule renewal save plan"
    if tickets >= 4:
        return "Clear support queue"
    if usage_down:
        return "Review adoption drop"
    return "Monitor"


def customer_health_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    accounts = load_json(data_dir, "accounts.json")
    tickets = load_json(data_dir, "tickets.json")
    incidents = load_json(data_dir, "incidents.json")
    usage = {str(row["account_id"]): row for row in load_json(data_dir, "usage.json")}
    renewal_payload = load_json(data_dir, "renewals.json")
    report_date = date.fromisoformat(str(renewal_payload["report_date"]))
    renewals = {str(row["account_id"]): row for row in renewal_payload["renewals"]}
    ticket_counts = _open_ticket_counts(tickets)
    incident_counts = _open_incident_counts(incidents)

    rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = str(account["account_id"])
        renewal_date = date.fromisoformat(str(renewals[account_id]["renewal_date"]))
        days = (renewal_date - report_date).days
        usage_row = usage[account_id]
        previous = int(usage_row["previous_period_events"])
        current = int(usage_row["current_period_events"])
        usage_down = current < previous
        usage_up = current > previous
        ticket_count = ticket_counts[account_id]
        incident_count = incident_counts[account_id]

        score = 0
        if days <= 30:
            score += 40
        if incident_count:
            score += 25
        score += min(30, ticket_count * 6)
        if usage_down:
            score += 20
        if account["plan"] == "enterprise" and usage_up:
            score -= 10
        score = min(100, max(0, score))
        band = _risk_band(score)
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
                "recommended_action": _action(
                    incident_count=incident_count,
                    days=days,
                    band=band,
                    tickets=ticket_count,
                    usage_down=usage_down,
                ),
            }
        )
    rows.sort(key=lambda row: (-int(row["risk_score"]), int(row["days_until_renewal"]), str(row["name"])))
    metrics = {
        "accounts": len(rows),
        "high-risk": sum(row["risk_band"] == "high" for row in rows),
        "open-tickets": sum(int(row["open_ticket_count"]) for row in rows),
        "renewals-30d": sum(0 <= int(row["days_until_renewal"]) <= 30 for row in rows),
    }
    return rows, metrics
PY

cat > workspace_app/screens/customer_health.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.customer_health import customer_health_rows


FIELDS = [
    ("name", "Account"),
    ("owner", "Owner"),
    ("plan", "Plan"),
    ("risk_score", "Risk Score"),
    ("risk_band", "Risk Band"),
    ("open_ticket_count", "Open Tickets"),
    ("open_incident_count", "Open Incidents"),
    ("days_until_renewal", "Renewal Days"),
    ("recommended_action", "Recommended Action"),
]


def _cell(field: str, value: object) -> str:
    return '<td data-field="%s">%s</td>' % (escape(field), escape(str(value)))


def _metric(key: str, value: object) -> str:
    return '<section class="stat-card" data-metric="%s">%s</section>' % (
        escape(key),
        escape(str(value)),
    )


def _table(rows: list[dict[str, object]]) -> str:
    headers = "".join("<th>%s</th>" % escape(label) for _, label in FIELDS)
    body = []
    for row in rows:
        cells = "".join(_cell(field, row[field]) for field, _ in FIELDS)
        body.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    return (
        '<table data-table="customer-health-risks"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
        % (headers, "".join(body))
    )


def render(data_dir: Path) -> str:
    rows, metrics = customer_health_rows(data_dir)
    cards = "".join(
        [
            _metric("accounts", metrics["accounts"]),
            _metric("high-risk", metrics["high-risk"]),
            _metric("open-tickets", metrics["open-tickets"]),
            _metric("renewals-30d", metrics["renewals-30d"]),
        ]
    )
    body = "<h1>Customer Health</h1><section class=\"metric-grid\">%s</section>%s" % (
        cards,
        _table(rows),
    )
    return render_layout("Customer Health", "/customer-health", body, data_screen="customer-health")
PY

python - <<'PY'
from pathlib import Path

routes = Path("workspace_app/routing.py")
text = routes.read_text()
text = text.replace(
    "from .screens import accounts, billing, home, reports, support",
    "from .screens import accounts, billing, customer_health, home, reports, support",
)
text = text.replace(
    '    "/reports": reports.render,\n}',
    '    "/reports": reports.render,\n    "/customer-health": customer_health.render,\n}',
)
routes.write_text(text)

nav = Path("workspace_app/nav.py")
text = nav.read_text()
text = text.replace(
    '    {"label": "Reports", "href": "/reports"},\n]',
    '    {"label": "Reports", "href": "/reports"},\n    {"label": "Customer Health", "href": "/customer-health"},\n]',
)
nav.write_text(text)
PY

cat > tests/test_customer_health.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CustomerHealthRouteTests(unittest.TestCase):
    def test_customer_health_route_renders_visible_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "health.html"
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
        self.assertIn('data-screen="customer-health"', html)
        self.assertIn("Customer Health", html)
        self.assertIn('data-account-id="acct-100"', html)
        self.assertIn("Escalate incident response", html)
        self.assertIn('href="/customer-health"', html)


if __name__ == "__main__":
    unittest.main()
PY

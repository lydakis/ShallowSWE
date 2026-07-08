#!/usr/bin/env bash
set -euo pipefail

mkdir -p workspace_app/selectors workspace_app/screens tests

cat > workspace_app/selectors/customer_health.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from workspace_app.data import load_json


RISK_ORDER = {"high": 0, "medium": 1, "low": 2}
RECOVERY_ORDER = {
    "contract_restore": 0,
    "incident_response": 1,
    "renewal_save": 2,
    "playbook_cleanup": 3,
    "engagement_restart": 4,
    "monitoring": 5,
}


def _risk_band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _latest_engagement(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        account_id = str(row["account_id"])
        if account_id not in latest or str(row["last_touch_at"]) > str(latest[account_id]["last_touch_at"]):
            latest[account_id] = row
    return latest


def _engagement_gap(
    report_date: date,
    engagement: dict[str, object] | None,
) -> str:
    if engagement is None:
        return "yes"
    last_touch = date.fromisoformat(str(engagement["last_touch_at"]))
    next_touch = date.fromisoformat(str(engagement["next_touch_at"]))
    return "yes" if (report_date - last_touch).days > 45 or next_touch < report_date else "no"


def _action(
    *,
    contract_active: bool,
    incident_count: int,
    overdue_playbooks: int,
    days: int,
    risk_band: str,
    open_tickets: int,
    engagement_gap: str,
    usage_down: bool,
) -> str:
    if not contract_active:
        return "Restore contract"
    if incident_count:
        return "Escalate incident response"
    if overdue_playbooks:
        return "Clear customer plan blockers"
    if days <= 30 and risk_band == "high":
        return "Schedule renewal save plan"
    if open_tickets >= 4:
        return "Clear support queue"
    if engagement_gap == "yes":
        return "Re-engage account owner"
    if usage_down:
        return "Review adoption drop"
    return "Monitor"


def customer_health_model(data_dir: str | Path) -> dict[str, object]:
    accounts = load_json(data_dir, "accounts.json")
    tickets = load_json(data_dir, "tickets.json")
    incidents = load_json(data_dir, "incidents.json")
    usage = {str(row["account_id"]): row for row in load_json(data_dir, "usage.json")}
    renewal_doc = load_json(data_dir, "renewals.json")
    report_date = date.fromisoformat(str(renewal_doc["report_date"]))
    renewals = {str(row["account_id"]): row for row in renewal_doc["renewals"]}
    contracts = {
        str(row["account_id"]): row for row in load_json(data_dir, "contracts.json")["contracts"]
    }
    engagements = _latest_engagement(load_json(data_dir, "engagements.json"))
    playbooks = load_json(data_dir, "playbooks.json")

    open_tickets: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket.get("status") == "open":
            open_tickets[str(ticket["account_id"])] += 1

    open_incidents: dict[str, int] = defaultdict(int)
    for incident in incidents:
        if incident.get("status") == "open" and incident.get("severity") in {"major", "critical"}:
            open_incidents[str(incident["account_id"])] += 1

    open_playbooks: dict[str, list[dict[str, object]]] = defaultdict(list)
    for playbook in playbooks:
        if playbook.get("status") != "done":
            open_playbooks[str(playbook["account_id"])].append(playbook)

    rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = str(account["account_id"])
        usage_row = usage[account_id]
        previous = int(usage_row["previous_period_events"])
        current = int(usage_row["current_period_events"])
        usage_down = current < previous
        usage_up = current > previous
        days = (
            date.fromisoformat(str(renewals[account_id]["renewal_date"])) - report_date
        ).days
        ticket_count = open_tickets[account_id]
        incident_count = open_incidents[account_id]
        contract = contracts[account_id]
        contract_status = str(contract["status"])
        contract_active = contract_status in {"active", "trialing"}
        renewal_date_text = str(renewals[account_id]["renewal_date"])
        account_playbooks = open_playbooks[account_id]
        overdue_count = sum(
            1 for playbook in account_playbooks if str(playbook["due_date"]) <= str(renewal_doc["report_date"])
        )
        next_due = min((str(playbook["due_date"]) for playbook in account_playbooks), default="")
        gap = _engagement_gap(report_date, engagements.get(account_id))

        score = 0
        if days <= 30:
            score += 40
        if incident_count:
            score += 25
        score += min(30, ticket_count * 6)
        if usage_down:
            score += 20
        if account.get("plan") == "enterprise" and usage_up:
            score -= 10
        if not contract_active:
            score += 35
        if overdue_count:
            score += 20
        if gap == "yes":
            score += 15
        score = max(0, min(100, score))
        risk_band = _risk_band(score)
        if not contract_active:
            recovery_stage = "contract_restore"
        elif incident_count:
            recovery_stage = "incident_response"
        elif days <= 30 and risk_band == "high":
            recovery_stage = "renewal_save"
        elif overdue_count:
            recovery_stage = "playbook_cleanup"
        elif gap == "yes":
            recovery_stage = "engagement_restart"
        else:
            recovery_stage = "monitoring"
        blocker_count = incident_count + overdue_count
        if not contract_active:
            blocker_count += 1
        if gap == "yes":
            blocker_count += 1
        if next_due:
            action_due = next_due
        elif recovery_stage in {"contract_restore", "incident_response"}:
            action_due = str(renewal_doc["report_date"])
        elif recovery_stage == "renewal_save":
            action_due = renewal_date_text
        else:
            action_due = ""
        executive_touch_due = (
            "yes"
            if int(contract["arr"]) >= 100000
            and (risk_band != "low" or days <= 30)
            else "no"
        )
        rows.append(
            {
                "account_id": account_id,
                "name": account["name"],
                "owner": account["owner"],
                "plan": account["plan"],
                "risk_score": score,
                "risk_band": risk_band,
                "open_ticket_count": ticket_count,
                "open_incident_count": incident_count,
                "days_until_renewal": days,
                "arr": int(contract["arr"]),
                "contract_status": contract_status,
                "engagement_gap": gap,
                "open_playbooks": len(account_playbooks),
                "overdue_playbooks": overdue_count,
                "next_playbook_due": next_due,
                "renewal_date": renewal_date_text,
                "recovery_stage": recovery_stage,
                "blocker_count": blocker_count,
                "action_due": action_due,
                "executive_touch_due": executive_touch_due,
                "recommended_action": _action(
                    contract_active=contract_active,
                    incident_count=incident_count,
                    overdue_playbooks=overdue_count,
                    days=days,
                    risk_band=risk_band,
                    open_tickets=ticket_count,
                    engagement_gap=gap,
                    usage_down=usage_down,
                ),
            }
        )

    rows.sort(key=lambda row: (-int(row["risk_score"]), int(row["days_until_renewal"]), str(row["name"])))
    dashboard_metrics = {
        "accounts": len(rows),
        "high-risk": sum(row["risk_band"] == "high" for row in rows),
        "open-tickets": sum(int(row["open_ticket_count"]) for row in rows),
        "renewals-30d": sum(0 <= int(row["days_until_renewal"]) <= 30 for row in rows),
    }

    action_rows = [
        {
            "account_id": row["account_id"],
            "account": row["name"],
            "owner": row["owner"],
            "risk_band": row["risk_band"],
            "recommended_action": row["recommended_action"],
            "next_playbook_due": row["next_playbook_due"],
            "overdue_playbooks": row["overdue_playbooks"],
            "open_playbooks": row["open_playbooks"],
            "arr": row["arr"],
            "engagement_gap": row["engagement_gap"],
        }
        for row in rows
        if row["recommended_action"] != "Monitor" or int(row["open_playbooks"]) > 0
    ]
    action_rows.sort(
        key=lambda row: (
            RISK_ORDER[str(row["risk_band"])],
            -int(row["overdue_playbooks"]),
            str(row["next_playbook_due"]) == "",
            str(row["next_playbook_due"]),
            str(row["account"]),
        )
    )
    action_metrics = {
        "actions": len(action_rows),
        "overdue-playbooks": sum(int(row["overdue_playbooks"]) for row in action_rows),
        "engagement-gaps": sum(row["engagement_gap"] == "yes" for row in action_rows),
        "arr-at-risk": sum(int(row["arr"]) for row in action_rows if row["risk_band"] != "low"),
    }

    owner_map: dict[str, dict[str, object]] = {}
    for row in rows:
        owner = str(row["owner"])
        bucket = owner_map.setdefault(
            owner,
            {
                "owner": owner,
                "accounts": 0,
                "high_risk_accounts": 0,
                "open_tickets": 0,
                "open_incidents": 0,
                "overdue_playbooks": 0,
                "engagement_gaps": 0,
                "arr_at_risk": 0,
                "next_playbook_due": "",
                "escalation_needed": "no",
            },
        )
        bucket["accounts"] = int(bucket["accounts"]) + 1
        bucket["high_risk_accounts"] = int(bucket["high_risk_accounts"]) + (
            1 if row["risk_band"] == "high" else 0
        )
        bucket["open_tickets"] = int(bucket["open_tickets"]) + int(row["open_ticket_count"])
        bucket["open_incidents"] = int(bucket["open_incidents"]) + int(row["open_incident_count"])
        bucket["overdue_playbooks"] = int(bucket["overdue_playbooks"]) + int(row["overdue_playbooks"])
        bucket["engagement_gaps"] = int(bucket["engagement_gaps"]) + (
            1 if row["engagement_gap"] == "yes" else 0
        )
        if row["risk_band"] != "low":
            bucket["arr_at_risk"] = int(bucket["arr_at_risk"]) + int(row["arr"])
        due = str(row["next_playbook_due"])
        if due and (not bucket["next_playbook_due"] or due < str(bucket["next_playbook_due"])):
            bucket["next_playbook_due"] = due

    owner_rows = list(owner_map.values())
    for row in owner_rows:
        if (
            int(row["high_risk_accounts"]) >= 1
            or int(row["overdue_playbooks"]) >= 2
            or int(row["open_incidents"]) >= 1
        ):
            row["escalation_needed"] = "yes"
    owner_rows.sort(
        key=lambda row: (
            0 if row["escalation_needed"] == "yes" else 1,
            -int(row["arr_at_risk"]),
            str(row["owner"]),
        )
    )
    owner_metrics = {
        "owners": len(owner_rows),
        "owners-with-escalations": sum(row["escalation_needed"] == "yes" for row in owner_rows),
        "overdue-playbooks": sum(int(row["overdue_playbooks"]) for row in owner_rows),
        "arr-at-risk": sum(int(row["arr_at_risk"]) for row in owner_rows),
    }

    recovery_rows = [
        {
            "account_id": row["account_id"],
            "account": row["name"],
            "owner": row["owner"],
            "risk_band": row["risk_band"],
            "recovery_stage": row["recovery_stage"],
            "blocker_count": row["blocker_count"],
            "action_due": row["action_due"],
            "executive_touch_due": row["executive_touch_due"],
            "arr": row["arr"],
            "recommended_action": row["recommended_action"],
        }
        for row in rows
        if row["recovery_stage"] != "monitoring" or row["risk_band"] != "low"
    ]
    recovery_rows.sort(
        key=lambda row: (
            RECOVERY_ORDER[str(row["recovery_stage"])],
            -int(row["blocker_count"]),
            str(row["action_due"]) == "",
            str(row["action_due"]),
            str(row["account"]),
        )
    )
    recovery_metrics = {
        "recovery-accounts": len(recovery_rows),
        "blocked-plans": sum(
            row["recovery_stage"] in {"contract_restore", "incident_response"}
            for row in recovery_rows
        ),
        "exec-touches": sum(row["executive_touch_due"] == "yes" for row in recovery_rows),
        "arr-in-plan": sum(int(row["arr"]) for row in recovery_rows),
    }
    dashboard_export_rows = [
        {
            "account_id": row["account_id"],
            "name": row["name"],
            "owner": row["owner"],
            "plan": row["plan"],
            "risk_score": row["risk_score"],
            "risk_band": row["risk_band"],
            "open_ticket_count": row["open_ticket_count"],
            "open_incident_count": row["open_incident_count"],
            "days_until_renewal": row["days_until_renewal"],
            "arr": row["arr"],
            "contract_status": row["contract_status"],
            "engagement_gap": row["engagement_gap"],
            "open_playbooks": row["open_playbooks"],
            "overdue_playbooks": row["overdue_playbooks"],
            "next_playbook_due": row["next_playbook_due"],
            "recommended_action": row["recommended_action"],
        }
        for row in rows
    ]
    export_payload = {
        "report_date": renewal_doc["report_date"],
        "dashboard_rows": dashboard_export_rows,
        "action_rows": action_rows,
        "owner_rows": owner_rows,
        "recovery_rows": recovery_rows,
        "summary": {
            "accounts": dashboard_metrics["accounts"],
            "high_risk": dashboard_metrics["high-risk"],
            "actions": action_metrics["actions"],
            "owners_with_escalations": owner_metrics["owners-with-escalations"],
            "recovery_accounts": recovery_metrics["recovery-accounts"],
            "arr_at_risk": owner_metrics["arr-at-risk"],
            "arr_in_recovery": recovery_metrics["arr-in-plan"],
        },
    }

    return {
        "dashboard_rows": rows,
        "dashboard_metrics": dashboard_metrics,
        "action_rows": action_rows,
        "action_metrics": action_metrics,
        "owner_rows": owner_rows,
        "owner_metrics": owner_metrics,
        "recovery_rows": recovery_rows,
        "recovery_metrics": recovery_metrics,
        "export_payload": export_payload,
    }
PY

cat > workspace_app/screens/customer_health.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.customer_health import customer_health_model


COLUMNS = [
    ("name", "Account"),
    ("owner", "Owner"),
    ("plan", "Plan"),
    ("risk_score", "Risk Score"),
    ("risk_band", "Risk Band"),
    ("open_ticket_count", "Open Tickets"),
    ("open_incident_count", "Open Incidents"),
    ("days_until_renewal", "Renewal Days"),
    ("arr", "ARR"),
    ("contract_status", "Contract"),
    ("engagement_gap", "Engagement Gap"),
    ("open_playbooks", "Open Playbooks"),
    ("overdue_playbooks", "Overdue Playbooks"),
    ("next_playbook_due", "Next Playbook Due"),
    ("recommended_action", "Recommended Action"),
]


def _metric(key: str, value: object) -> str:
    return '<section data-metric="%s">%s</section>' % (escape(key), escape(str(value)))


def _table(rows: list[dict[str, object]]) -> str:
    headers = "".join("<th>%s</th>" % escape(label) for _, label in COLUMNS)
    body = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field, _ in COLUMNS
        )
        body.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    return '<table data-table="customer-health-risks"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body),
    )


def render(data_dir: Path) -> str:
    model = customer_health_model(data_dir)
    metrics = model["dashboard_metrics"]
    rows = model["dashboard_rows"]
    cards = "".join(_metric(key, metrics[key]) for key in ["accounts", "high-risk", "open-tickets", "renewals-30d"])
    body = '<h1>Customer Health</h1><section class="metric-grid">%s</section>%s' % (cards, _table(rows))
    return render_layout("Customer Health", "/customer-health", body, data_screen="customer-health")
PY

cat > workspace_app/screens/customer_health_actions.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.customer_health import customer_health_model


COLUMNS = [
    ("account", "Account"),
    ("owner", "Owner"),
    ("risk_band", "Risk Band"),
    ("recommended_action", "Recommended Action"),
    ("next_playbook_due", "Next Playbook Due"),
    ("overdue_playbooks", "Overdue Playbooks"),
    ("open_playbooks", "Open Playbooks"),
    ("arr", "ARR"),
    ("engagement_gap", "Engagement Gap"),
]


def _metric(key: str, value: object) -> str:
    return '<section data-metric="%s">%s</section>' % (escape(key), escape(str(value)))


def _table(rows: list[dict[str, object]]) -> str:
    headers = "".join("<th>%s</th>" % escape(label) for _, label in COLUMNS)
    body = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field, _ in COLUMNS
        )
        body.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    return '<table data-table="customer-health-actions"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body),
    )


def render(data_dir: Path) -> str:
    model = customer_health_model(data_dir)
    metrics = model["action_metrics"]
    rows = model["action_rows"]
    cards = "".join(_metric(key, metrics[key]) for key in ["actions", "overdue-playbooks", "engagement-gaps", "arr-at-risk"])
    body = '<h1>Customer Health Actions</h1><section class="metric-grid">%s</section>%s' % (cards, _table(rows))
    return render_layout("Customer Health Actions", "/customer-health/actions", body, data_screen="customer-health-actions")
PY

cat > workspace_app/screens/customer_health_owner_queue.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.customer_health import customer_health_model


COLUMNS = [
    ("owner", "Owner"),
    ("accounts", "Accounts"),
    ("high_risk_accounts", "High Risk Accounts"),
    ("open_tickets", "Open Tickets"),
    ("open_incidents", "Open Incidents"),
    ("overdue_playbooks", "Overdue Playbooks"),
    ("engagement_gaps", "Engagement Gaps"),
    ("arr_at_risk", "ARR At Risk"),
    ("next_playbook_due", "Next Playbook Due"),
    ("escalation_needed", "Escalation Needed"),
]


def _metric(key: str, value: object) -> str:
    return '<section data-metric="%s">%s</section>' % (escape(key), escape(str(value)))


def _table(rows: list[dict[str, object]]) -> str:
    headers = "".join("<th>%s</th>" % escape(label) for _, label in COLUMNS)
    body = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field, _ in COLUMNS
        )
        body.append('<tr data-owner="%s">%s</tr>' % (escape(str(row["owner"])), cells))
    return '<table data-table="customer-health-owner-queue"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body),
    )


def render(data_dir: Path) -> str:
    model = customer_health_model(data_dir)
    metrics = model["owner_metrics"]
    rows = model["owner_rows"]
    cards = "".join(_metric(key, metrics[key]) for key in ["owners", "owners-with-escalations", "overdue-playbooks", "arr-at-risk"])
    body = '<h1>Customer Health Owner Queue</h1><section class="metric-grid">%s</section>%s' % (cards, _table(rows))
    return render_layout("Customer Health Owner Queue", "/customer-health/owner-queue", body, data_screen="customer-health-owner-queue")
PY

cat > workspace_app/screens/customer_health_recovery_plan.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.customer_health import customer_health_model


COLUMNS = [
    ("account", "Account"),
    ("owner", "Owner"),
    ("risk_band", "Risk Band"),
    ("recovery_stage", "Recovery Stage"),
    ("blocker_count", "Blockers"),
    ("action_due", "Action Due"),
    ("executive_touch_due", "Executive Touch Due"),
    ("arr", "ARR"),
    ("recommended_action", "Recommended Action"),
]


def _metric(key: str, value: object) -> str:
    return '<section data-metric="%s">%s</section>' % (escape(key), escape(str(value)))


def _table(rows: list[dict[str, object]]) -> str:
    headers = "".join("<th>%s</th>" % escape(label) for _, label in COLUMNS)
    body = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field, _ in COLUMNS
        )
        body.append('<tr data-account-id="%s">%s</tr>' % (escape(str(row["account_id"])), cells))
    return '<table data-table="customer-health-recovery-plan"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body),
    )


def render(data_dir: Path) -> str:
    model = customer_health_model(data_dir)
    metrics = model["recovery_metrics"]
    rows = model["recovery_rows"]
    cards = "".join(_metric(key, metrics[key]) for key in ["recovery-accounts", "blocked-plans", "exec-touches", "arr-in-plan"])
    body = '<h1>Customer Health Recovery Plan</h1><section class="metric-grid">%s</section>%s' % (cards, _table(rows))
    return render_layout(
        "Customer Health Recovery Plan",
        "/customer-health/recovery-plan",
        body,
        data_screen="customer-health-recovery-plan",
    )
PY

python - <<'PY'
from pathlib import Path

routes = Path("workspace_app/routing.py")
text = routes.read_text()
import_line = "from .screens import "
for line in text.splitlines():
    if line.startswith(import_line):
        names = [part.strip() for part in line[len(import_line):].split(",")]
        for name in [
            "customer_health",
            "customer_health_actions",
            "customer_health_owner_queue",
            "customer_health_recovery_plan",
        ]:
            if name not in names:
                names.append(name)
        text = text.replace(line, import_line + ", ".join(sorted(names)))
        break
route_map = {
    '"/customer-health"': "customer_health.render",
    '"/customer-health/actions"': "customer_health_actions.render",
    '"/customer-health/owner-queue"': "customer_health_owner_queue.render",
    '"/customer-health/recovery-plan"': "customer_health_recovery_plan.render",
}
for route, renderer in route_map.items():
    if route not in text:
        text = text.replace("}\n\n\ndef route_names", f'    {route}: {renderer},\n}}\n\n\ndef route_names')
routes.write_text(text)

nav = Path("workspace_app/nav.py")
text = nav.read_text()
if 'href": "/customer-health"' not in text:
    text = text.replace(
        "]\n",
        '    {"label": "Customer Health", "href": "/customer-health"},\n]\n',
    )
nav.write_text(text)

cli = Path("workspace_app/cli.py")
text = cli.read_text()
if "customer_health_model" not in text:
    text = text.replace(
        "from .routing import render_route, route_names\n",
        "from .routing import render_route, route_names\nfrom .selectors.customer_health import customer_health_model\nimport json\n",
    )
if "--export-customer-health" not in text:
    text = text.replace(
        'parser.add_argument("--list-routes", action="store_true")\n',
        'parser.add_argument("--list-routes", action="store_true")\n'
        '    parser.add_argument("--export-customer-health")\n',
    )
if "args.export_customer_health" not in text:
    text = text.replace(
        'if args.list_routes:\n        print("\\n".join(route_names()))\n        return 0\n\n    html = render_route(args.route, args.data_dir)\n',
        'if args.list_routes:\n        print("\\n".join(route_names()))\n        return 0\n\n'
        '    if args.export_customer_health:\n'
        '        output = Path(args.export_customer_health)\n'
        '        output.parent.mkdir(parents=True, exist_ok=True)\n'
        '        payload = customer_health_model(args.data_dir)["export_payload"]\n'
        '        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n")\n'
        '        return 0\n\n'
        '    html = render_route(args.route, args.data_dir)\n',
    )
cli.write_text(text)
PY

cat > tests/test_customer_health.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CustomerHealthRoutesTest(unittest.TestCase):
    def render(self, route: str) -> str:
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
                    "/app/fixtures/visible",
                    "--output",
                    str(output),
                ],
                check=True,
            )
            return output.read_text()

    def test_customer_health_routes_render(self) -> None:
        expected = {
            "/customer-health": ('data-screen="customer-health"', 'data-table="customer-health-risks"'),
            "/customer-health/actions": ('data-screen="customer-health-actions"', 'data-table="customer-health-actions"'),
            "/customer-health/owner-queue": ('data-screen="customer-health-owner-queue"', 'data-table="customer-health-owner-queue"'),
            "/customer-health/recovery-plan": ('data-screen="customer-health-recovery-plan"', 'data-table="customer-health-recovery-plan"'),
        }
        for route, needles in expected.items():
            with self.subTest(route=route):
                html = self.render(route)
                self.assertIn('href="/customer-health"', html)
                for needle in needles:
                    self.assertIn(needle, html)

    def test_customer_health_export_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "customer-health.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "workspace_app.cli",
                    "--data-dir",
                    "/app/fixtures/visible",
                    "--export-customer-health",
                    str(output),
                ],
                check=True,
            )
            self.assertIn('"recovery_rows"', output.read_text())


if __name__ == "__main__":
    unittest.main()
PY

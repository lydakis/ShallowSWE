#!/usr/bin/env bash
set -euo pipefail

cat >> workspace_app/nav.py <<'PY'

NAV_ITEMS.append({"label": "Seat Compliance", "href": "/seat-compliance"})
PY

cat > workspace_app/selectors/seat_compliance.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from workspace_app.data import load_json


STATUS_ORDER = {
    "blocked": 0,
    "over_limit": 1,
    "identity_review": 2,
    "cleanup": 3,
    "accepted_exception": 4,
    "renewal_review": 5,
    "ok": 6,
}
DUE_BY_STATUS = {
    "blocked": 0,
    "over_limit": 3,
    "identity_review": 5,
    "cleanup": 7,
    "accepted_exception": 10,
    "renewal_review": 14,
}


def _latest_allocations(allocations: list[dict[str, Any]], report_date: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in allocations:
        if str(row["effective_on"]) > report_date:
            continue
        account_id = str(row["account_id"])
        current = latest.get(account_id)
        if current is None or str(row["effective_on"]) > str(current["effective_on"]):
            latest[account_id] = row
    return latest


def seat_rows(data_dir: str | Path) -> tuple[
    list[dict[str, object]],
    dict[str, int],
    list[dict[str, object]],
    dict[str, int],
    list[dict[str, object]],
    dict[str, int],
    list[dict[str, object]],
    dict[str, int],
]:
    accounts = load_json(data_dir, "accounts.json")
    subscriptions_doc = load_json(data_dir, "subscriptions.json")
    plans = load_json(data_dir, "plan_limits.json")
    allocations = load_json(data_dir, "allocations.json")
    users = load_json(data_dir, "users.json")
    invitations = load_json(data_dir, "invitations.json")
    exceptions = load_json(data_dir, "exceptions.json")
    tickets = load_json(data_dir, "tickets.json")
    report_date_text = str(subscriptions_doc["report_date"])
    report_date = date.fromisoformat(report_date_text)
    subscriptions = {str(row["account_id"]): row for row in subscriptions_doc["subscriptions"]}
    latest_alloc = _latest_allocations(allocations, report_date_text)

    active_exceptions: dict[str, set[str]] = defaultdict(set)
    for row in exceptions:
        if str(row["expires_on"]) >= report_date_text:
            active_exceptions[str(row["account_id"])].add(str(row["control"]))

    by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in users:
        by_account[str(row["account_id"])].append(row)
    invites_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in invitations:
        invites_by_account[str(row["account_id"])].append(row)
    tickets_by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tickets:
        tickets_by_account[str(row["account_id"])].append(row)

    rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = str(account["account_id"])
        plan = plans[str(account["plan"])]
        subscription = subscriptions[account_id]
        serviceable = subscription["status"] in {"active", "trialing"}
        renewal_days = (date.fromisoformat(str(subscription["renewal_date"])) - report_date).days
        seat_limit = int(latest_alloc.get(account_id, {}).get("seat_limit_override", plan["seat_limit"]))
        contractor_limit = int(plan["contractor_limit"])
        active_users = [row for row in by_account.get(account_id, []) if row["status"] == "active"]
        active_contractors = [row for row in active_users if row["user_type"] == "contractor"]
        pending_invites = [
            row
            for row in invites_by_account.get(account_id, [])
            if row["status"] == "pending" and str(row["expires_on"]) >= report_date_text
        ]
        expired_invites = [
            row
            for row in invites_by_account.get(account_id, [])
            if row["status"] == "pending" and str(row["expires_on"]) < report_date_text
        ]
        pending_contractors = [row for row in pending_invites if row["user_type"] == "contractor"]
        billable = len(active_users) + len(pending_invites)
        contractor_seats = len(active_contractors) + len(pending_contractors)
        sso_gaps = 0
        if plan["included_sso"]:
            sso_gaps = sum(
                1
                for row in active_users
                if row["user_type"] == "employee" and not bool(row["sso_enabled"])
            )
        open_priority = sum(
            1
            for row in tickets_by_account.get(account_id, [])
            if row["status"] == "open" and row["priority"] in {"p0", "p1"}
        )
        raw: list[str] = []
        if not serviceable:
            raw.append("subscription_not_serviceable")
        if billable > seat_limit:
            raw.append("seat_overage")
        if contractor_seats > contractor_limit:
            raw.append("contractor_overage")
        if sso_gaps > 0:
            raw.append("sso_gap")
        if expired_invites:
            raw.append("expired_invites")
        exemptable = {"seat_overage", "contractor_overage", "sso_gap"}
        exception_controls = [
            code for code in raw if code in exemptable and code in active_exceptions.get(account_id, set())
        ]
        missing = [code for code in raw if code not in set(exception_controls)]
        if "subscription_not_serviceable" in missing:
            status = "blocked"
            action = "Restore subscription"
        elif "seat_overage" in missing:
            status = "over_limit"
            action = "Reduce or approve seat overage"
        elif "contractor_overage" in missing:
            status = "over_limit"
            action = "Reduce or approve contractor access"
        elif "sso_gap" in missing:
            status = "identity_review"
            action = "Fix SSO enrollment"
        elif "expired_invites" in missing:
            status = "cleanup"
            action = "Expire stale invitations"
        elif raw and not missing:
            status = "accepted_exception"
            action = "Review accepted exception"
        elif renewal_days <= 30 and billable >= 0.9 * seat_limit:
            status = "renewal_review"
            action = "Prepare renewal capacity review"
        else:
            status = "ok"
            action = "Monitor"
        rows.append(
            {
                "account_id": account_id,
                "account": account["name"],
                "owner": account["owner"],
                "plan": account["plan"],
                "segment": account["segment"],
                "status": status,
                "seat_limit": seat_limit,
                "billable_seats": billable,
                "seat_delta": billable - seat_limit,
                "contractor_limit": contractor_limit,
                "contractor_seats": contractor_seats,
                "contractor_delta": contractor_seats - contractor_limit,
                "active_users": len(active_users),
                "pending_invites": len(pending_invites),
                "expired_invites": len(expired_invites),
                "sso_gaps": sso_gaps,
                "renewal_days": renewal_days,
                "open_priority_tickets": open_priority,
                "arr": int(account["arr"]),
                "reason_codes": ",".join(missing) if missing else "none",
                "exception_controls": ",".join(exception_controls) if exception_controls else "none",
                "recommended_action": action,
            }
        )
    rows.sort(key=lambda row: (STATUS_ORDER[str(row["status"])], -int(row["seat_delta"]), str(row["account"])))

    main_metrics = {
        "accounts": len(rows),
        "over-limit": sum(row["status"] == "over_limit" for row in rows),
        "identity-reviews": sum(row["status"] == "identity_review" for row in rows),
        "accepted-exceptions": sum(row["status"] == "accepted_exception" for row in rows),
    }
    overage_rows = [row for row in rows if row["status"] != "ok"]
    overage_rows.sort(
        key=lambda row: (
            STATUS_ORDER[str(row["status"])],
            -int(row["seat_delta"]),
            -int(row["contractor_delta"]),
            str(row["account"]),
        )
    )
    overage_metrics = {
        "review-accounts": len(overage_rows),
        "seats-over": sum(max(0, int(row["seat_delta"])) for row in overage_rows),
        "contractors-over": sum(max(0, int(row["contractor_delta"])) for row in overage_rows),
        "blocked": sum(row["status"] == "blocked" for row in overage_rows),
    }

    by_owner: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_owner[str(row["owner"])].append(row)
    owner_rows: list[dict[str, object]] = []
    for owner, owned in by_owner.items():
        blocked = sum(row["status"] == "blocked" for row in owned)
        over_limit = sum(row["status"] == "over_limit" for row in owned)
        identity = sum(row["status"] == "identity_review" for row in owned)
        accepted = sum(row["status"] == "accepted_exception" for row in owned)
        seats_over = sum(max(0, int(row["seat_delta"])) for row in owned)
        contractors_over = sum(max(0, int(row["contractor_delta"])) for row in owned)
        arr_at_risk = sum(int(row["arr"]) for row in owned if row["status"] != "ok")
        escalation = "yes" if blocked >= 1 or over_limit >= 1 or identity >= 2 else "no"
        owner_rows.append(
            {
                "owner": owner,
                "accounts": len(owned),
                "blocked_accounts": blocked,
                "over_limit_accounts": over_limit,
                "identity_review_accounts": identity,
                "accepted_exceptions": accepted,
                "seats_over": seats_over,
                "contractors_over": contractors_over,
                "sso_gaps": sum(int(row["sso_gaps"]) for row in owned),
                "open_priority_tickets": sum(int(row["open_priority_tickets"]) for row in owned),
                "arr_at_risk": arr_at_risk,
                "next_renewal_days": min(int(row["renewal_days"]) for row in owned),
                "escalation_needed": escalation,
            }
        )
    owner_rows.sort(key=lambda row: (0 if row["escalation_needed"] == "yes" else 1, -int(row["arr_at_risk"]), str(row["owner"])))
    owner_metrics = {
        "owners": len(owner_rows),
        "owners-with-escalations": sum(row["escalation_needed"] == "yes" for row in owner_rows),
        "seats-over": sum(int(row["seats_over"]) for row in owner_rows),
        "arr-at-risk": sum(int(row["arr_at_risk"]) for row in owner_rows),
    }
    escalated_owners = {row["owner"] for row in owner_rows if row["escalation_needed"] == "yes"}
    action_rows: list[dict[str, object]] = []
    for row in rows:
        if row["status"] == "ok":
            continue
        action_rows.append(
            {
                "account_id": row["account_id"],
                "account": row["account"],
                "owner": row["owner"],
                "status": row["status"],
                "reason_codes": row["reason_codes"],
                "exception_controls": row["exception_controls"],
                "primary_action": row["recommended_action"],
                "due_in_days": DUE_BY_STATUS[str(row["status"])],
                "escalation_needed": "yes" if row["owner"] in escalated_owners else "no",
                "arr": row["arr"],
            }
        )
    action_rows.sort(
        key=lambda row: (
            STATUS_ORDER[str(row["status"])],
            int(row["due_in_days"]),
            -int(row["arr"]),
            str(row["account"]),
        )
    )
    action_metrics = {
        "action-accounts": len(action_rows),
        "due-now": sum(int(row["due_in_days"]) == 0 for row in action_rows),
        "owner-escalations": sum(row["escalation_needed"] == "yes" for row in action_rows),
        "arr-at-risk": sum(int(row["arr"]) for row in action_rows),
    }
    return (
        rows,
        main_metrics,
        overage_rows,
        overage_metrics,
        owner_rows,
        owner_metrics,
        action_rows,
        action_metrics,
    )
PY

cat > /tmp/write_seat_screens.py <<'PY'
from pathlib import Path


def write(path: str, text: str) -> None:
    Path(path).write_text(text)


COMMON = '''from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.seat_compliance import seat_rows


def metric_block(metrics: dict[str, int], keys: list[str]) -> str:
    return '<section class="metrics">%s</section>' % ''.join(
        '<span data-metric="%s">%s</span>' % (escape(key), escape(str(metrics[key])))
        for key in keys
    )


def table(table_key: str, row_key: str, fields: list[str], rows: list[dict[str, object]]) -> str:
    header = ''.join('<th>%s</th>' % escape(field.replace("_", " ").title()) for field in fields)
    body = []
    for row in rows:
        cells = ''.join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field in fields
        )
        if row_key == "owner":
            attrs = 'data-owner="%s"' % escape(str(row["owner"]))
        else:
            attrs = 'data-account-id="%s"' % escape(str(row["account_id"]))
        body.append('<tr %s>%s</tr>' % (attrs, cells))
    return '<table data-table="%s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        escape(table_key), header, ''.join(body)
    )
'''

write(
    "workspace_app/screens/seat_compliance.py",
    COMMON + '''
METRICS = ["accounts", "over-limit", "identity-reviews", "accepted-exceptions"]
FIELDS = [
    "account", "owner", "plan", "segment", "status", "seat_limit", "billable_seats",
    "seat_delta", "contractor_limit", "contractor_seats", "contractor_delta",
    "active_users", "pending_invites", "expired_invites", "sso_gaps", "renewal_days",
    "open_priority_tickets", "arr", "reason_codes", "exception_controls",
    "recommended_action",
]


def render(data_dir: Path) -> str:
    rows, metrics, _, _, _, _, _, _ = seat_rows(data_dir)
    body = "<h1>Seat Compliance</h1>%s%s" % (
        metric_block(metrics, METRICS),
        table("seat-compliance", "account", FIELDS, rows),
    )
    return render_layout("Seat Compliance", "/seat-compliance", body, data_screen="seat-compliance")
''',
)
write(
    "workspace_app/screens/seat_compliance_overages.py",
    COMMON + '''
METRICS = ["review-accounts", "seats-over", "contractors-over", "blocked"]
FIELDS = [
    "account", "owner", "status", "seat_delta", "contractor_delta", "sso_gaps",
    "expired_invites", "open_priority_tickets", "reason_codes", "exception_controls",
    "recommended_action",
]


def render(data_dir: Path) -> str:
    _, _, rows, metrics, _, _, _, _ = seat_rows(data_dir)
    body = "<h1>Seat Compliance Overages</h1>%s%s" % (
        metric_block(metrics, METRICS),
        table("seat-compliance-overages", "account", FIELDS, rows),
    )
    return render_layout(
        "Seat Compliance Overages",
        "/seat-compliance/overages",
        body,
        data_screen="seat-compliance-overages",
    )
''',
)
write(
    "workspace_app/screens/seat_compliance_owner_queue.py",
    COMMON + '''
METRICS = ["owners", "owners-with-escalations", "seats-over", "arr-at-risk"]
FIELDS = [
    "owner", "accounts", "blocked_accounts", "over_limit_accounts",
    "identity_review_accounts", "accepted_exceptions", "seats_over",
    "contractors_over", "sso_gaps", "open_priority_tickets", "arr_at_risk",
    "next_renewal_days", "escalation_needed",
]


def render(data_dir: Path) -> str:
    _, _, _, _, rows, metrics, _, _ = seat_rows(data_dir)
    body = "<h1>Seat Compliance Owner Queue</h1>%s%s" % (
        metric_block(metrics, METRICS),
        table("seat-compliance-owner-queue", "owner", FIELDS, rows),
    )
    return render_layout(
        "Seat Compliance Owner Queue",
        "/seat-compliance/owner-queue",
        body,
        data_screen="seat-compliance-owner-queue",
    )
''',
)
write(
    "workspace_app/screens/seat_compliance_action_log.py",
    COMMON + '''
METRICS = ["action-accounts", "due-now", "owner-escalations", "arr-at-risk"]
FIELDS = [
    "account", "owner", "status", "reason_codes", "exception_controls",
    "primary_action", "due_in_days", "escalation_needed", "arr",
]


def render(data_dir: Path) -> str:
    _, _, _, _, _, _, rows, metrics = seat_rows(data_dir)
    body = "<h1>Seat Compliance Action Log</h1>%s%s" % (
        metric_block(metrics, METRICS),
        table("seat-compliance-action-log", "account", FIELDS, rows),
    )
    return render_layout(
        "Seat Compliance Action Log",
        "/seat-compliance/action-log",
        body,
        data_screen="seat-compliance-action-log",
    )
''',
)
PY
python /tmp/write_seat_screens.py

mkdir -p workspace_app/exports
cat > workspace_app/exports/__init__.py <<'PY'
PY
cat > workspace_app/exports/seat_compliance.py <<'PY'
from __future__ import annotations

from pathlib import Path
import json

from workspace_app.selectors.seat_compliance import seat_rows

ACTION_FIELDS = [
    "account",
    "owner",
    "status",
    "reason_codes",
    "exception_controls",
    "primary_action",
    "due_in_days",
    "escalation_needed",
    "arr",
]
OWNER_FIELDS = [
    "owner",
    "accounts",
    "blocked_accounts",
    "over_limit_accounts",
    "identity_review_accounts",
    "accepted_exceptions",
    "seats_over",
    "contractors_over",
    "sso_gaps",
    "open_priority_tickets",
    "arr_at_risk",
    "next_renewal_days",
    "escalation_needed",
]


def payload(data_dir: str | Path) -> dict[str, object]:
    _, _, _, _, owner_rows, _, action_rows, action_metrics = seat_rows(data_dir)
    return {
        "schema_version": "seat_compliance_export.v1",
        "summary": action_metrics,
        "actions": [{field: row[field] for field in ACTION_FIELDS} for row in action_rows],
        "owner_queue": [{field: row[field] for field in OWNER_FIELDS} for row in owner_rows],
    }


def write_export(data_dir: str | Path, output: str | Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload(data_dir), indent=2, sort_keys=True) + "\n")
PY

python - <<'PY'
from pathlib import Path

path = Path("workspace_app/cli.py")
text = path.read_text()
if 'parser.add_argument("--export-seat-compliance")' not in text:
    text = text.replace(
        '    parser.add_argument("--output")\n    parser.add_argument("--list-routes", action="store_true")\n',
        '    parser.add_argument("--output")\n    parser.add_argument("--export-seat-compliance")\n    parser.add_argument("--list-routes", action="store_true")\n',
    )
if "write_export(args.data_dir, args.export_seat_compliance)" not in text:
    text = text.replace(
        '    html = render_route(args.route, args.data_dir)\n',
        '    if args.export_seat_compliance:\n        from workspace_app.exports.seat_compliance import write_export\n\n        write_export(args.data_dir, args.export_seat_compliance)\n        return 0\n\n    html = render_route(args.route, args.data_dir)\n',
    )
if 'parser.add_argument("--export-seat-compliance")' not in text:
    raise SystemExit("failed to add --export-seat-compliance CLI argument")
if "write_export(args.data_dir, args.export_seat_compliance)" not in text:
    raise SystemExit("failed to add seat compliance export branch")
path.write_text(text)
PY

cat >> workspace_app/routing.py <<'PY'

from .screens import (
    seat_compliance,
    seat_compliance_action_log,
    seat_compliance_overages,
    seat_compliance_owner_queue,
)

ROUTES.update(
    {
        "/seat-compliance": seat_compliance.render,
        "/seat-compliance/action-log": seat_compliance_action_log.render,
        "/seat-compliance/overages": seat_compliance_overages.render,
        "/seat-compliance/owner-queue": seat_compliance_owner_queue.render,
    }
)
PY

cat > tests/test_seat_compliance_routes.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class SeatComplianceRouteTests(unittest.TestCase):
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

    def test_new_routes_render(self) -> None:
        for route, screen in [
            ("/seat-compliance", "seat-compliance"),
            ("/seat-compliance/overages", "seat-compliance-overages"),
            ("/seat-compliance/owner-queue", "seat-compliance-owner-queue"),
            ("/seat-compliance/action-log", "seat-compliance-action-log"),
        ]:
            with self.subTest(route=route):
                self.assertIn(f'data-screen="{screen}"', self.render(route))

    def test_nav_and_route_listing(self) -> None:
        routes = subprocess.run(
            [sys.executable, "-m", "workspace_app.cli", "--list-routes"],
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        self.assertIn("/seat-compliance", routes)
        self.assertIn("/seat-compliance/action-log", routes)
        self.assertIn('href="/seat-compliance"', self.render("/seat-compliance"))
        self.assertIn("Seat Compliance", self.render("/seat-compliance"))

    def test_export_command_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "seat-review.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "workspace_app.cli",
                    "--data-dir",
                    "/app/fixtures/visible",
                    "--export-seat-compliance",
                    str(output),
                ],
                check=True,
            )
            text = output.read_text()
            self.assertTrue(text.endswith("\n"))
            self.assertIn('"schema_version": "seat_compliance_export.v1"', text)
            self.assertIn('"actions"', text)
            self.assertIn('"owner_queue"', text)


if __name__ == "__main__":
    unittest.main()
PY

python -m unittest discover -s tests

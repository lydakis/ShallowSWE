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
import re
import subprocess
import sys
import tempfile
import unittest


APP = Path(os.environ.get("APP_DIR", "/app"))
STATUS_ORDER = {
    "blocked": 0,
    "over_limit": 1,
    "identity_review": 2,
    "cleanup": 3,
    "accepted_exception": 4,
    "renewal_review": 5,
    "ok": 6,
}
MAIN_FIELDS = [
    "account",
    "owner",
    "plan",
    "segment",
    "status",
    "seat_limit",
    "billable_seats",
    "seat_delta",
    "contractor_limit",
    "contractor_seats",
    "contractor_delta",
    "active_users",
    "pending_invites",
    "expired_invites",
    "sso_gaps",
    "renewal_days",
    "open_priority_tickets",
    "arr",
    "reason_codes",
    "exception_controls",
    "recommended_action",
]
OVERAGE_FIELDS = [
    "account",
    "owner",
    "status",
    "seat_delta",
    "contractor_delta",
    "sso_gaps",
    "expired_invites",
    "open_priority_tickets",
    "reason_codes",
    "exception_controls",
    "recommended_action",
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
DUE_BY_STATUS = {
    "blocked": 0,
    "over_limit": 3,
    "identity_review": 5,
    "cleanup": 7,
    "accepted_exception": 10,
    "renewal_review": 14,
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


def write_fixture(root: Path, *, variant: str) -> Path:
    data_dir = root / variant
    data_dir.mkdir()
    if variant == "hidden-a":
        accounts = [
            {"account_id": "ha-1", "name": "Aster Legal", "owner": "Ava Lee", "plan": "enterprise", "segment": "regulated", "arr": 180000},
            {"account_id": "ha-2", "name": "Basin Solar", "owner": "Bo Kim", "plan": "growth", "segment": "commercial", "arr": 78000},
            {"account_id": "ha-3", "name": "Cobalt Health", "owner": "Ava Lee", "plan": "enterprise", "segment": "strategic", "arr": 260000},
        ]
        subscriptions = {
            "report_date": "2026-09-05",
            "subscriptions": [
                {"account_id": "ha-1", "status": "active", "renewal_date": "2026-09-20"},
                {"account_id": "ha-2", "status": "active", "renewal_date": "2026-10-20"},
                {"account_id": "ha-3", "status": "canceled", "renewal_date": "2026-09-12"},
            ],
        }
        plans = {
            "enterprise": {"seat_limit": 3, "contractor_limit": 1, "included_sso": True},
            "growth": {"seat_limit": 2, "contractor_limit": 0, "included_sso": True},
        }
        allocations = [
            {"account_id": "ha-1", "seat_limit_override": 4, "effective_on": "2026-09-01", "source": "contract"},
            {"account_id": "ha-2", "seat_limit_override": 5, "effective_on": "2026-10-01", "source": "future"},
        ]
        users = [
            {"user_id": "ha-u1", "account_id": "ha-1", "status": "active", "user_type": "employee", "sso_enabled": True},
            {"user_id": "ha-u2", "account_id": "ha-1", "status": "active", "user_type": "employee", "sso_enabled": False},
            {"user_id": "ha-u3", "account_id": "ha-1", "status": "active", "user_type": "contractor", "sso_enabled": False},
            {"user_id": "ha-u4", "account_id": "ha-2", "status": "active", "user_type": "contractor", "sso_enabled": True},
            {"user_id": "ha-u5", "account_id": "ha-2", "status": "active", "user_type": "employee", "sso_enabled": True},
            {"user_id": "ha-u6", "account_id": "ha-3", "status": "active", "user_type": "employee", "sso_enabled": False},
        ]
        invites = [
            {"invite_id": "ha-i1", "account_id": "ha-1", "status": "pending", "expires_on": "2026-09-10", "user_type": "employee"},
            {"invite_id": "ha-i2", "account_id": "ha-1", "status": "pending", "expires_on": "2026-09-01", "user_type": "contractor"},
            {"invite_id": "ha-i3", "account_id": "ha-2", "status": "pending", "expires_on": "2026-09-30", "user_type": "contractor"},
        ]
        exceptions = [
            {"account_id": "ha-1", "control": "sso_gap", "expires_on": "2026-09-30", "reason": "idp rollout", "approver": "security"},
            {"account_id": "ha-2", "control": "contractor_overage", "expires_on": "2026-09-12", "reason": "agency surge", "approver": "success"},
        ]
        tickets = [
            {"account_id": "ha-3", "status": "open", "priority": "p0"},
            {"account_id": "ha-2", "status": "open", "priority": "p1"},
        ]
    else:
        accounts = [
            {"account_id": "hb-1", "name": "Dune Works", "owner": "Cy Rao", "plan": "starter", "segment": "smb", "arr": 16000},
            {"account_id": "hb-2", "name": "Elm Finance", "owner": "Diya Shah", "plan": "enterprise", "segment": "regulated", "arr": 340000},
            {"account_id": "hb-3", "name": "Fjord Games", "owner": "Cy Rao", "plan": "growth", "segment": "commercial", "arr": 92000},
        ]
        subscriptions = {
            "report_date": "2026-11-10",
            "subscriptions": [
                {"account_id": "hb-1", "status": "trialing", "renewal_date": "2026-11-25"},
                {"account_id": "hb-2", "status": "active", "renewal_date": "2026-12-20"},
                {"account_id": "hb-3", "status": "active", "renewal_date": "2026-11-20"},
            ],
        }
        plans = {
            "starter": {"seat_limit": 2, "contractor_limit": 0, "included_sso": False},
            "growth": {"seat_limit": 4, "contractor_limit": 1, "included_sso": True},
            "enterprise": {"seat_limit": 6, "contractor_limit": 2, "included_sso": True},
        }
        allocations = [
            {"account_id": "hb-2", "seat_limit_override": 8, "effective_on": "2026-10-01", "source": "contract"},
            {"account_id": "hb-3", "seat_limit_override": 5, "effective_on": "2026-11-01", "source": "amendment"},
        ]
        users = [
            {"user_id": "hb-u1", "account_id": "hb-1", "status": "active", "user_type": "employee", "sso_enabled": False},
            {"user_id": "hb-u2", "account_id": "hb-1", "status": "active", "user_type": "contractor", "sso_enabled": False},
            {"user_id": "hb-u3", "account_id": "hb-2", "status": "active", "user_type": "employee", "sso_enabled": True},
            {"user_id": "hb-u4", "account_id": "hb-2", "status": "active", "user_type": "employee", "sso_enabled": True},
            {"user_id": "hb-u5", "account_id": "hb-3", "status": "active", "user_type": "employee", "sso_enabled": False},
            {"user_id": "hb-u6", "account_id": "hb-3", "status": "active", "user_type": "employee", "sso_enabled": False},
            {"user_id": "hb-u7", "account_id": "hb-3", "status": "active", "user_type": "contractor", "sso_enabled": True},
        ]
        invites = [
            {"invite_id": "hb-i1", "account_id": "hb-1", "status": "pending", "expires_on": "2026-11-01", "user_type": "employee"},
            {"invite_id": "hb-i2", "account_id": "hb-3", "status": "pending", "expires_on": "2026-11-18", "user_type": "employee"},
            {"invite_id": "hb-i3", "account_id": "hb-3", "status": "pending", "expires_on": "2026-11-18", "user_type": "contractor"},
        ]
        exceptions = [
            {"account_id": "hb-3", "control": "seat_overage", "expires_on": "2026-12-01", "reason": "launch event", "approver": "vp"},
        ]
        tickets = [
            {"account_id": "hb-1", "status": "open", "priority": "p2"},
            {"account_id": "hb-3", "status": "open", "priority": "p1"},
        ]
    write_json(data_dir / "accounts.json", accounts)
    write_json(data_dir / "subscriptions.json", subscriptions)
    write_json(data_dir / "plan_limits.json", plans)
    write_json(data_dir / "allocations.json", allocations)
    write_json(data_dir / "users.json", users)
    write_json(data_dir / "invitations.json", invites)
    write_json(data_dir / "exceptions.json", exceptions)
    write_json(data_dir / "tickets.json", tickets)
    return data_dir


def load(data_dir: Path, name: str) -> object:
    return json.loads((data_dir / name).read_text())


def expected(data_dir: Path) -> dict[str, object]:
    accounts = load(data_dir, "accounts.json")
    subscriptions_doc = load(data_dir, "subscriptions.json")
    plans = load(data_dir, "plan_limits.json")
    allocations = load(data_dir, "allocations.json")
    users = load(data_dir, "users.json")
    invitations = load(data_dir, "invitations.json")
    exceptions = load(data_dir, "exceptions.json")
    tickets = load(data_dir, "tickets.json")
    report_date = date.fromisoformat(subscriptions_doc["report_date"])
    subscriptions = {row["account_id"]: row for row in subscriptions_doc["subscriptions"]}

    latest_alloc: dict[str, dict[str, object]] = {}
    for row in allocations:
        if row["effective_on"] > subscriptions_doc["report_date"]:
            continue
        current = latest_alloc.get(row["account_id"])
        if current is None or row["effective_on"] > current["effective_on"]:
            latest_alloc[row["account_id"]] = row

    active_exceptions: dict[str, set[str]] = defaultdict(set)
    for row in exceptions:
        if row["expires_on"] >= subscriptions_doc["report_date"]:
            active_exceptions[row["account_id"]].add(row["control"])

    users_by_account: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in users:
        users_by_account[row["account_id"]].append(row)
    invites_by_account: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in invitations:
        invites_by_account[row["account_id"]].append(row)
    tickets_by_account: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in tickets:
        tickets_by_account[row["account_id"]].append(row)

    rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = account["account_id"]
        plan = plans[account["plan"]]
        subscription = subscriptions[account_id]
        serviceable = subscription["status"] in {"active", "trialing"}
        renewal_days = (date.fromisoformat(subscription["renewal_date"]) - report_date).days
        seat_limit = int(
            latest_alloc.get(account_id, {}).get("seat_limit_override", plan["seat_limit"])
        )
        contractor_limit = int(plan["contractor_limit"])
        account_users = users_by_account.get(account_id, [])
        active_users = [row for row in account_users if row["status"] == "active"]
        active_contractors = [
            row for row in active_users if row["user_type"] == "contractor"
        ]
        account_invites = invites_by_account.get(account_id, [])
        pending_invites = [
            row
            for row in account_invites
            if row["status"] == "pending" and row["expires_on"] >= subscriptions_doc["report_date"]
        ]
        expired_invites = [
            row
            for row in account_invites
            if row["status"] == "pending" and row["expires_on"] < subscriptions_doc["report_date"]
        ]
        pending_contractors = [
            row for row in pending_invites if row["user_type"] == "contractor"
        ]
        billable = len(active_users) + len(pending_invites)
        contractor_seats = len(active_contractors) + len(pending_contractors)
        sso_gaps = 0
        if plan["included_sso"]:
            sso_gaps = sum(
                1
                for row in active_users
                if row["user_type"] == "employee" and not row["sso_enabled"]
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
    rows.sort(key=lambda row: (STATUS_ORDER[row["status"]], -int(row["seat_delta"]), row["account"]))
    overage_rows = [row for row in rows if row["status"] != "ok"]
    overage_rows.sort(
        key=lambda row: (
            STATUS_ORDER[row["status"]],
            -int(row["seat_delta"]),
            -int(row["contractor_delta"]),
            row["account"],
        )
    )

    by_owner: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_owner[row["owner"]].append(row)
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
    owner_rows.sort(key=lambda row: (0 if row["escalation_needed"] == "yes" else 1, -int(row["arr_at_risk"]), row["owner"]))
    escalated_owners = {
        row["owner"] for row in owner_rows if row["escalation_needed"] == "yes"
    }
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
                "due_in_days": DUE_BY_STATUS[row["status"]],
                "escalation_needed": "yes" if row["owner"] in escalated_owners else "no",
                "arr": row["arr"],
            }
        )
    action_rows.sort(
        key=lambda row: (
            STATUS_ORDER[row["status"]],
            int(row["due_in_days"]),
            -int(row["arr"]),
            row["account"],
        )
    )
    action_metrics = {
        "action-accounts": len(action_rows),
        "due-now": sum(int(row["due_in_days"]) == 0 for row in action_rows),
        "owner-escalations": sum(row["escalation_needed"] == "yes" for row in action_rows),
        "arr-at-risk": sum(int(row["arr"]) for row in action_rows),
    }
    return {
        "main_rows": rows,
        "main_metrics": {
            "accounts": len(rows),
            "over-limit": sum(row["status"] == "over_limit" for row in rows),
            "identity-reviews": sum(row["status"] == "identity_review" for row in rows),
            "accepted-exceptions": sum(row["status"] == "accepted_exception" for row in rows),
        },
        "overage_rows": overage_rows,
        "overage_metrics": {
            "review-accounts": len(overage_rows),
            "seats-over": sum(max(0, int(row["seat_delta"])) for row in overage_rows),
            "contractors-over": sum(max(0, int(row["contractor_delta"])) for row in overage_rows),
            "blocked": sum(row["status"] == "blocked" for row in overage_rows),
        },
        "owner_rows": owner_rows,
        "owner_metrics": {
            "owners": len(owner_rows),
            "owners-with-escalations": sum(row["escalation_needed"] == "yes" for row in owner_rows),
            "seats-over": sum(int(row["seats_over"]) for row in owner_rows),
            "arr-at-risk": sum(int(row["arr_at_risk"]) for row in owner_rows),
        },
        "action_rows": action_rows,
        "action_metrics": action_metrics,
        "export": {
            "schema_version": "seat_compliance_export.v1",
            "summary": action_metrics,
            "actions": project_rows(action_rows, ACTION_FIELDS),
            "owner_queue": project_rows(owner_rows, OWNER_FIELDS),
        },
    }


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.screen = ""
        self.h1 = ""
        self.metrics: dict[str, str] = {}
        self.rows_by_account: dict[str, dict[str, str]] = {}
        self.rows_by_owner: dict[str, dict[str, str]] = {}
        self._metric: str | None = None
        self._metric_depth = 0
        self._field: str | None = None
        self._row_key: tuple[str, str] | None = None
        self._table: str | None = None
        self._h1 = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v or "" for k, v in attrs}
        if self._metric is not None:
            self._metric_depth += 1
        if tag == "main":
            self.screen = attr.get("data-screen", "")
        if tag == "table":
            self._table = attr.get("data-table")
        if tag == "tr":
            if "data-account-id" in attr:
                self._row_key = ("account", attr["data-account-id"])
                self.rows_by_account.setdefault(attr["data-account-id"], {})
            elif "data-owner" in attr:
                self._row_key = ("owner", attr["data-owner"])
                self.rows_by_owner.setdefault(attr["data-owner"], {})
        if tag == "h1":
            self._h1 = True
            self._buf = []
        if "data-metric" in attr:
            self._metric = attr["data-metric"]
            self._metric_depth = 1
            self._buf = []
        if "data-field" in attr:
            self._field = attr["data-field"]
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._metric or self._field or self._h1:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        text = "".join(self._buf).strip()
        if tag == "h1" and self._h1:
            self.h1 = text
            self._h1 = False
            self._buf = []
        if self._metric:
            self._metric_depth -= 1
            if self._metric_depth == 0:
                numbers = re.findall(r"-?\d+", text)
                self.metrics[self._metric] = numbers[-1] if numbers else text
                self._metric = None
                self._buf = []
        if self._field:
            if self._row_key and self._row_key[0] == "account":
                self.rows_by_account[self._row_key[1]][self._field] = text
            elif self._row_key and self._row_key[0] == "owner":
                self.rows_by_owner[self._row_key[1]][self._field] = text
            self._field = None
            self._buf = []
        if tag == "tr":
            self._row_key = None
        if tag == "table":
            self._table = None


def render(route: str, data_dir: Path) -> PageParser:
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
                str(data_dir),
                "--output",
                str(output),
            ],
            cwd=APP,
            check=True,
        )
        parser = PageParser()
        parser.feed(output.read_text())
        return parser


def assert_rows(testcase: unittest.TestCase, actual: dict[str, dict[str, str]], expected_rows: list[dict[str, object]], key: str, fields: list[str]) -> None:
    testcase.assertEqual(list(actual), [str(row[key]) for row in expected_rows])
    for row in expected_rows:
        got = actual[str(row[key])]
        testcase.assertEqual(set(got), set(fields))
        for field in fields:
            testcase.assertEqual(got[field], str(row[field]), f"{row[key]} {field}")


def project_rows(rows: list[dict[str, object]], fields: list[str]) -> list[dict[str, object]]:
    return [{field: row[field] for field in fields} for row in rows]


def export_payload(data_dir: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "seat-review.json"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "workspace_app.cli",
                "--data-dir",
                str(data_dir),
                "--export-seat-compliance",
                str(output),
            ],
            cwd=APP,
            check=True,
        )
        text = output.read_text()
        if not text.endswith("\n"):
            raise AssertionError("export JSON must end with a newline")
        return json.loads(text)


class SeatComplianceVerifier(unittest.TestCase):
    def assert_pages(self, data_dir: Path) -> None:
        exp = expected(data_dir)
        main = render("/seat-compliance", data_dir)
        self.assertEqual(main.screen, "seat-compliance")
        self.assertEqual(main.h1, "Seat Compliance")
        self.assertEqual(main.metrics, {k: str(v) for k, v in exp["main_metrics"].items()})
        assert_rows(self, main.rows_by_account, exp["main_rows"], "account_id", MAIN_FIELDS)

        overages = render("/seat-compliance/overages", data_dir)
        self.assertEqual(overages.screen, "seat-compliance-overages")
        self.assertEqual(overages.h1, "Seat Compliance Overages")
        self.assertEqual(overages.metrics, {k: str(v) for k, v in exp["overage_metrics"].items()})
        assert_rows(self, overages.rows_by_account, exp["overage_rows"], "account_id", OVERAGE_FIELDS)

        owners = render("/seat-compliance/owner-queue", data_dir)
        self.assertEqual(owners.screen, "seat-compliance-owner-queue")
        self.assertEqual(owners.h1, "Seat Compliance Owner Queue")
        self.assertEqual(owners.metrics, {k: str(v) for k, v in exp["owner_metrics"].items()})
        assert_rows(self, owners.rows_by_owner, exp["owner_rows"], "owner", OWNER_FIELDS)

        actions = render("/seat-compliance/action-log", data_dir)
        self.assertEqual(actions.screen, "seat-compliance-action-log")
        self.assertEqual(actions.h1, "Seat Compliance Action Log")
        self.assertEqual(actions.metrics, {k: str(v) for k, v in exp["action_metrics"].items()})
        assert_rows(self, actions.rows_by_account, exp["action_rows"], "account_id", ACTION_FIELDS)

        self.assertEqual(export_payload(data_dir), exp["export"])

    def test_visible_fixture_and_app_tests(self) -> None:
        routes = subprocess.run(
            [sys.executable, "-m", "workspace_app.cli", "--list-routes"],
            cwd=APP,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        self.assertIn("/seat-compliance", routes)
        self.assertIn("/seat-compliance/overages", routes)
        self.assertIn("/seat-compliance/owner-queue", routes)
        self.assertIn("/seat-compliance/action-log", routes)
        nav_html = render("/seat-compliance", APP / "fixtures" / "visible")
        self.assert_pages(APP / "fixtures" / "visible")
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=APP, check=True)

    def test_hidden_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assert_pages(write_fixture(root, variant="hidden-a"))
            self.assert_pages(write_fixture(root, variant="hidden-b"))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(SeatComplianceVerifier)
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


FIELDS = {
    "name",
    "owner",
    "plan",
    "risk_score",
    "risk_band",
    "open_ticket_count",
    "open_incident_count",
    "days_until_renewal",
    "recommended_action",
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


def write_fixture(root: Path, *, variant: str) -> Path:
    data_dir = root / variant
    data_dir.mkdir()
    if variant == "hidden-a":
        write_json(
            data_dir / "accounts.json",
            [
                {"account_id": "ha-1", "name": "Atlas Cloud", "owner": "Rin Vale", "plan": "enterprise"},
                {"account_id": "ha-2", "name": "Beacon Foods", "owner": "Elle Ortiz", "plan": "pro"},
                {"account_id": "ha-3", "name": "Cinder Bank", "owner": "Kai Moore", "plan": "enterprise"},
                {"account_id": "ha-4", "name": "Drift Labs", "owner": "Samir Iqbal", "plan": "starter"},
                {"account_id": "ha-5", "name": "Ember Media", "owner": "Lina Fox", "plan": "pro"},
            ],
        )
        write_json(
            data_dir / "tickets.json",
            [
                {"ticket_id": "HA1-T1", "account_id": "ha-1", "status": "open"},
                {"ticket_id": "HA1-T2", "account_id": "ha-1", "status": "closed"},
                {"ticket_id": "HA2-T1", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T2", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T3", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T4", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T5", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA4-T1", "account_id": "ha-4", "status": "open"},
            ],
        )
        write_json(
            data_dir / "incidents.json",
            [
                {"incident_id": "HA1-I1", "account_id": "ha-1", "status": "open", "severity": "critical"},
                {"incident_id": "HA3-I1", "account_id": "ha-3", "status": "open", "severity": "minor"},
                {"incident_id": "HA5-I1", "account_id": "ha-5", "status": "resolved", "severity": "major"},
            ],
        )
        write_json(
            data_dir / "usage.json",
            [
                {"account_id": "ha-1", "previous_period_events": 5000, "current_period_events": 5200},
                {"account_id": "ha-2", "previous_period_events": 2200, "current_period_events": 1700},
                {"account_id": "ha-3", "previous_period_events": 1000, "current_period_events": 1040},
                {"account_id": "ha-4", "previous_period_events": 400, "current_period_events": 300},
                {"account_id": "ha-5", "previous_period_events": 750, "current_period_events": 750},
            ],
        )
        write_json(
            data_dir / "renewals.json",
            {
                "report_date": "2026-08-01",
                "renewals": [
                    {"account_id": "ha-1", "renewal_date": "2026-08-18"},
                    {"account_id": "ha-2", "renewal_date": "2026-12-20"},
                    {"account_id": "ha-3", "renewal_date": "2026-08-11"},
                    {"account_id": "ha-4", "renewal_date": "2026-09-18"},
                    {"account_id": "ha-5", "renewal_date": "2026-08-30"},
                ],
            },
        )
    else:
        write_json(
            data_dir / "accounts.json",
            [
                {"account_id": "hb-1", "name": "Northwind Systems", "owner": "Priya Sen", "plan": "enterprise"},
                {"account_id": "hb-2", "name": "Oak & Pine", "owner": "Theo Grant", "plan": "starter"},
                {"account_id": "hb-3", "name": "Pioneer Robotics", "owner": "Mika Lane", "plan": "pro"},
            ],
        )
        write_json(
            data_dir / "tickets.json",
            [
                {"ticket_id": "HB1-T1", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T2", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T3", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T4", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T5", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T6", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB2-T1", "account_id": "hb-2", "status": "closed"},
                {"ticket_id": "HB3-T1", "account_id": "hb-3", "status": "open"},
            ],
        )
        write_json(
            data_dir / "incidents.json",
            [
                {"incident_id": "HB3-I1", "account_id": "hb-3", "status": "open", "severity": "major"},
            ],
        )
        write_json(
            data_dir / "usage.json",
            [
                {"account_id": "hb-1", "previous_period_events": 1200, "current_period_events": 800},
                {"account_id": "hb-2", "previous_period_events": 500, "current_period_events": 505},
                {"account_id": "hb-3", "previous_period_events": 300, "current_period_events": 200},
            ],
        )
        write_json(
            data_dir / "renewals.json",
            {
                "report_date": "2026-10-10",
                "renewals": [
                    {"account_id": "hb-1", "renewal_date": "2026-10-25"},
                    {"account_id": "hb-2", "renewal_date": "2026-12-30"},
                    {"account_id": "hb-3", "renewal_date": "2026-10-22"},
                ],
            },
        )
    return data_dir


def load_json(data_dir: Path, name: str) -> object:
    return json.loads((data_dir / name).read_text())


def expected(data_dir: Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    accounts = load_json(data_dir, "accounts.json")
    tickets = load_json(data_dir, "tickets.json")
    incidents = load_json(data_dir, "incidents.json")
    usage = {row["account_id"]: row for row in load_json(data_dir, "usage.json")}
    renewal_payload = load_json(data_dir, "renewals.json")
    report_date = date.fromisoformat(renewal_payload["report_date"])
    renewals = {row["account_id"]: row for row in renewal_payload["renewals"]}

    open_tickets: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket["status"] == "open":
            open_tickets[ticket["account_id"]] += 1

    open_incidents: dict[str, int] = defaultdict(int)
    for incident in incidents:
        if incident["status"] == "open" and incident["severity"] in {"major", "critical"}:
            open_incidents[incident["account_id"]] += 1

    rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = account["account_id"]
        renewal_date = date.fromisoformat(renewals[account_id]["renewal_date"])
        days = (renewal_date - report_date).days
        account_usage = usage[account_id]
        usage_down = account_usage["current_period_events"] < account_usage["previous_period_events"]
        usage_up = account_usage["current_period_events"] > account_usage["previous_period_events"]
        ticket_count = open_tickets[account_id]
        incident_count = open_incidents[account_id]
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
        if score >= 70:
            band = "high"
        elif score >= 40:
            band = "medium"
        else:
            band = "low"
        if incident_count:
            action = "Escalate incident response"
        elif days <= 30 and band == "high":
            action = "Schedule renewal save plan"
        elif ticket_count >= 4:
            action = "Clear support queue"
        elif usage_down:
            action = "Review adoption drop"
        else:
            action = "Monitor"
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
                "recommended_action": action,
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


class HealthParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, object] | None] = []
        self.h1: list[str] = []
        self.screen_seen = False
        self.table_seen = False
        self.nav_links: list[tuple[str, str]] = []
        self.metrics: dict[str, str] = defaultdict(str)
        self.rows: dict[str, dict[str, str]] = defaultdict(lambda: defaultdict(str))
        self.row_order: list[str] = []

    def _current_row(self) -> str | None:
        for item in reversed(self.stack):
            if item and item[0] == "row":
                return str(item[1])
        return None

    def handle_starttag(self, tag: str, attrs_raw: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_raw}
        capture: tuple[str, object] | None = None
        if tag == "main" and attrs.get("data-screen") == "customer-health":
            self.screen_seen = True
        if tag == "table" and attrs.get("data-table") == "customer-health-risks":
            self.table_seen = True
        if tag == "h1":
            capture = ("h1", None)
        elif tag == "a" and attrs.get("href"):
            capture = ("nav", attrs["href"])
        elif "data-metric" in attrs:
            capture = ("metric", attrs["data-metric"])
        elif tag == "tr" and "data-account-id" in attrs:
            account_id = attrs["data-account-id"]
            capture = ("row", account_id)
            self.row_order.append(account_id)
        elif "data-field" in attrs:
            account_id = self._current_row()
            if account_id is not None:
                capture = ("field", (account_id, attrs["data-field"]))
        self.stack.append(capture)

    def handle_endtag(self, tag: str) -> None:
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        for item in reversed(self.stack):
            if item is None:
                continue
            kind, payload = item
            if kind == "h1":
                self.h1.append(text)
                return
            if kind == "nav":
                self.nav_links.append((text, str(payload)))
                return
            if kind == "metric":
                self.metrics[str(payload)] += text
                return
            if kind == "field":
                account_id, field = payload
                self.rows[str(account_id)][str(field)] += text
                return


def render(route: str, data_dir: Path) -> str:
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
            check=True,
        )
        return output.read_text()


def parse(html: str) -> HealthParser:
    parser = HealthParser()
    parser.feed(html)
    return parser


class CustomerHealthVerifier(unittest.TestCase):
    def assert_dashboard(self, data_dir: Path) -> None:
        parser = parse(render("/customer-health", data_dir))
        expected_rows, expected_metrics = expected(data_dir)
        self.assertTrue(parser.screen_seen)
        self.assertTrue(parser.table_seen)
        self.assertIn(("Customer Health", "/customer-health"), parser.nav_links)
        self.assertEqual(" ".join(parser.h1), "Customer Health")
        self.assertEqual(parser.metrics, {key: str(value) for key, value in expected_metrics.items()})
        self.assertEqual(parser.row_order, [str(row["account_id"]) for row in expected_rows])
        self.assertEqual(set(parser.rows), {str(row["account_id"]) for row in expected_rows})
        for row in expected_rows:
            account_id = str(row["account_id"])
            self.assertEqual(set(parser.rows[account_id]), FIELDS)
            for field in FIELDS:
                self.assertEqual(parser.rows[account_id][field], str(row[field]), (account_id, field))

    def test_source_structure_and_unittest_regression(self) -> None:
        self.assertTrue(Path("/app/workspace_app/screens/customer_health.py").exists())
        self.assertTrue(Path("/app/workspace_app/selectors/customer_health.py").exists())
        test_files = list(Path("/app/tests").glob("test*.py"))
        combined_tests = "\n".join(path.read_text() for path in test_files)
        self.assertIn("/customer-health", combined_tests)
        self.assertIn("Customer Health", combined_tests)
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], check=True)

    def test_existing_routes_still_render_and_nav_includes_new_item(self) -> None:
        for route, screen in [
            ("/", "home"),
            ("/accounts", "accounts"),
            ("/support", "support"),
            ("/billing", "billing"),
            ("/reports", "reports"),
        ]:
            with self.subTest(route=route):
                html = render(route, Path("/app/fixtures/visible"))
                self.assertIn(f'data-screen="{screen}"', html)
                self.assertIn('href="/customer-health"', html)
                self.assertIn("Customer Health", html)

    def test_visible_fixture_exact(self) -> None:
        self.assert_dashboard(Path("/app/fixtures/visible"))

    def test_hidden_fixtures_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assert_dashboard(write_fixture(root, variant="hidden-a"))
            self.assert_dashboard(write_fixture(root, variant="hidden-b"))


if __name__ == "__main__":
    unittest.main()
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"

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


ENTITLEMENT_FIELDS = {
    "workspace",
    "owner",
    "plan",
    "feature",
    "effective_enabled",
    "limit",
    "usage",
    "status",
    "override_days_remaining",
    "reason_codes",
    "recommended_action",
}
OVERRIDE_FIELDS = {"workspace", "owner", "feature", "enabled", "days_remaining", "status", "reason"}
STATUS_ORDER = {"blocked": 0, "over_limit": 1, "override_review": 2, "ok": 3}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


def write_fixture(root: Path, *, variant: str) -> Path:
    data_dir = root / variant
    data_dir.mkdir()
    if variant == "hidden-a":
        workspaces = [
            {"workspace_id": "ha-1", "name": "Arc Legal", "owner": "Ava Lee", "plan": "enterprise"},
            {"workspace_id": "ha-2", "name": "Basin Energy", "owner": "Ben Cruz", "plan": "growth"},
        ]
        subscriptions = {
            "report_date": "2026-09-01",
            "subscriptions": [
                {"workspace_id": "ha-1", "status": "trialing", "renewal_date": "2026-09-14"},
                {"workspace_id": "ha-2", "status": "canceled", "renewal_date": "2026-09-30"},
            ],
        }
        plans = {
            "enterprise": {
                "audit_logs": {"enabled": True, "limit": None},
                "sso": {"enabled": True, "limit": None},
                "api_access": {"enabled": True, "limit": 20000},
            },
            "growth": {
                "audit_logs": {"enabled": True, "limit": 60},
                "sso": {"enabled": False, "limit": None},
                "api_access": {"enabled": True, "limit": 5000},
            },
        }
        usage = [
            {"workspace_id": "ha-1", "feature": "api_access", "current_usage": 21000},
            {"workspace_id": "ha-2", "feature": "api_access", "current_usage": 100},
            {"workspace_id": "ha-2", "feature": "audit_logs", "current_usage": 70},
        ]
        overrides = [
            {"workspace_id": "ha-1", "feature": "sso", "enabled": False, "expires_on": "2026-09-20", "reason": "security review"},
            {"workspace_id": "ha-1", "feature": "audit_logs", "enabled": True, "expires_on": "2026-09-08", "reason": "short extension"},
            {"workspace_id": "ha-2", "feature": "sso", "enabled": True, "expires_on": "2026-09-10", "reason": "ignored by canceled subscription"},
        ]
    else:
        workspaces = [
            {"workspace_id": "hb-1", "name": "Cobalt Studio", "owner": "Ira Moss", "plan": "starter"},
            {"workspace_id": "hb-2", "name": "Dune Robotics", "owner": "Nia Shah", "plan": "pro"},
            {"workspace_id": "hb-3", "name": "Elm School", "owner": "Nia Shah", "plan": "pro"},
        ]
        subscriptions = {
            "report_date": "2026-11-10",
            "subscriptions": [
                {"workspace_id": "hb-1", "status": "active", "renewal_date": "2026-12-01"},
                {"workspace_id": "hb-2", "status": "active", "renewal_date": "2026-11-28"},
                {"workspace_id": "hb-3", "status": "past_due", "renewal_date": "2026-11-15"},
            ],
        }
        plans = {
            "starter": {
                "audit_logs": {"enabled": False, "limit": 20},
                "api_access": {"enabled": True, "limit": 1000},
                "sso": {"enabled": False, "limit": None},
            },
            "pro": {
                "audit_logs": {"enabled": True, "limit": 120},
                "api_access": {"enabled": True, "limit": 8000},
                "sso": {"enabled": True, "limit": None},
            },
        }
        usage = [
            {"workspace_id": "hb-1", "feature": "api_access", "current_usage": 400},
            {"workspace_id": "hb-2", "feature": "api_access", "current_usage": 9000},
            {"workspace_id": "hb-2", "feature": "audit_logs", "current_usage": 110},
            {"workspace_id": "hb-3", "feature": "sso", "current_usage": 0},
        ]
        overrides = [
            {"workspace_id": "hb-1", "feature": "sso", "enabled": True, "expires_on": "2026-11-20", "reason": "migration"},
            {"workspace_id": "hb-2", "feature": "api_access", "enabled": True, "expires_on": "2026-12-15", "reason": "scale test"},
            {"workspace_id": "hb-1", "feature": "audit_logs", "enabled": True, "expires_on": "2026-10-01", "reason": "expired"},
        ]
    write_json(data_dir / "workspaces.json", workspaces)
    write_json(data_dir / "subscriptions.json", subscriptions)
    write_json(data_dir / "plan_features.json", plans)
    write_json(data_dir / "usage.json", usage)
    write_json(data_dir / "overrides.json", overrides)
    return data_dir


def load_json(data_dir: Path, name: str) -> object:
    return json.loads((data_dir / name).read_text())


def expected(data_dir: Path) -> dict[str, object]:
    workspaces = load_json(data_dir, "workspaces.json")
    subscription_doc = load_json(data_dir, "subscriptions.json")
    plans = load_json(data_dir, "plan_features.json")
    usage_rows = load_json(data_dir, "usage.json")
    overrides = load_json(data_dir, "overrides.json")
    report_date = date.fromisoformat(subscription_doc["report_date"])
    subscriptions = {row["workspace_id"]: row for row in subscription_doc["subscriptions"]}
    workspace_by_id = {row["workspace_id"]: row for row in workspaces}
    usage = {
        (row["workspace_id"], row["feature"]): int(row["current_usage"])
        for row in usage_rows
    }
    expired_count = 0
    active_overrides: dict[tuple[str, str], dict[str, object]] = {}
    for override in overrides:
        expires = date.fromisoformat(override["expires_on"])
        if expires < report_date:
            expired_count += 1
            continue
        key = (override["workspace_id"], override["feature"])
        current = active_overrides.get(key)
        if current is None or override["expires_on"] > current["expires_on"]:
            active_overrides[key] = override

    features = sorted({feature for plan in plans.values() for feature in plan})
    entitlement_rows: list[dict[str, object]] = []
    for workspace in workspaces:
        workspace_id = workspace["workspace_id"]
        plan_name = workspace["plan"]
        subscription = subscriptions[workspace_id]
        serviceable = subscription["status"] in {"active", "trialing"}
        for feature in features:
            spec = plans[plan_name][feature]
            override = active_overrides.get((workspace_id, feature))
            enabled = bool(spec["enabled"])
            override_days: int | str = ""
            if override is not None:
                enabled = bool(override["enabled"])
                override_days = (date.fromisoformat(override["expires_on"]) - report_date).days
            limit = spec["limit"]
            current_usage = usage.get((workspace_id, feature), 0)
            reasons: list[str] = []
            if not serviceable:
                reasons.append("subscription_not_serviceable")
            if not enabled:
                reasons.append("feature_disabled")
            if limit is not None and current_usage > int(limit):
                reasons.append("usage_over_limit")
            if override is not None and int(override_days) <= 14:
                reasons.append("override_expiring")

            if not serviceable:
                status = "blocked"
                action = "Restore subscription"
            elif not enabled:
                status = "blocked"
                action = "Review feature access"
            elif limit is not None and current_usage > int(limit):
                status = "over_limit"
                action = "Contact owner about limit"
            elif override is not None and int(override_days) <= 14:
                status = "override_review"
                action = "Review temporary override"
            else:
                status = "ok"
                action = "Monitor"
            entitlement_rows.append(
                {
                    "workspace_id": workspace_id,
                    "workspace": workspace["name"],
                    "owner": workspace["owner"],
                    "plan": plan_name,
                    "feature": feature,
                    "effective_enabled": str(enabled).lower(),
                    "limit": "unlimited" if limit is None else int(limit),
                    "usage": current_usage,
                    "status": status,
                    "override_days_remaining": override_days,
                    "reason_codes": ",".join(reasons) if reasons else "none",
                    "recommended_action": action,
                }
            )
    entitlement_rows.sort(
        key=lambda row: (
            STATUS_ORDER[str(row["status"])],
            str(row["owner"]),
            str(row["workspace"]),
            str(row["feature"]),
        )
    )
    entitlement_metrics = {
        "workspaces": len(workspaces),
        "blocked": sum(row["status"] == "blocked" for row in entitlement_rows),
        "over-limit": sum(row["status"] == "over_limit" for row in entitlement_rows),
        "overrides-expiring": sum(row["status"] == "override_review" for row in entitlement_rows),
    }

    override_rows: list[dict[str, object]] = []
    for (workspace_id, feature), override in active_overrides.items():
        workspace = workspace_by_id[workspace_id]
        days = (date.fromisoformat(override["expires_on"]) - report_date).days
        override_rows.append(
            {
                "workspace_id": workspace_id,
                "workspace": workspace["name"],
                "owner": workspace["owner"],
                "feature": feature,
                "enabled": str(bool(override["enabled"])).lower(),
                "days_remaining": days,
                "status": "expiring" if days <= 14 else "active",
                "reason": override["reason"],
            }
        )
    override_rows.sort(
        key=lambda row: (int(row["days_remaining"]), str(row["owner"]), str(row["workspace"]), str(row["feature"]))
    )
    override_metrics = {
        "active-overrides": len(override_rows),
        "expiring-overrides": sum(row["status"] == "expiring" for row in override_rows),
        "expired-overrides": expired_count,
    }
    return {
        "entitlement_rows": entitlement_rows,
        "entitlement_metrics": entitlement_metrics,
        "override_rows": override_rows,
        "override_metrics": override_metrics,
    }


class PageParser(HTMLParser):
    def __init__(self, *, screen: str, table: str) -> None:
        super().__init__()
        self.screen = screen
        self.table = table
        self.stack: list[tuple[str, object] | None] = []
        self.screen_seen = False
        self.table_seen = False
        self.h1: list[str] = []
        self.nav_links: list[tuple[str, str]] = []
        self.metrics: dict[str, str] = defaultdict(str)
        self.rows: dict[tuple[str, str], dict[str, str]] = defaultdict(lambda: defaultdict(str))
        self.row_order: list[tuple[str, str]] = []

    def _current_row(self) -> tuple[str, str] | None:
        for item in reversed(self.stack):
            if item and item[0] == "row":
                return item[1]  # type: ignore[return-value]
        return None

    def handle_starttag(self, tag: str, attrs_raw: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_raw}
        capture: tuple[str, object] | None = None
        if tag == "main" and attrs.get("data-screen") == self.screen:
            self.screen_seen = True
        if tag == "table" and attrs.get("data-table") == self.table:
            self.table_seen = True
        if tag == "h1":
            capture = ("h1", None)
        elif tag == "a" and attrs.get("href"):
            capture = ("nav", attrs["href"])
        elif "data-metric" in attrs:
            capture = ("metric", attrs["data-metric"])
        elif tag == "tr" and "data-workspace-id" in attrs and "data-feature" in attrs:
            key = (attrs["data-workspace-id"], attrs["data-feature"])
            capture = ("row", key)
            self.row_order.append(key)
        elif "data-field" in attrs:
            key = self._current_row()
            if key is not None:
                self.rows[key][attrs["data-field"]] += ""
                capture = ("field", (key, attrs["data-field"]))
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
                key, field = payload
                self.rows[key][str(field)] += text
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


class EntitlementsVerifier(unittest.TestCase):
    def assert_entitlements(self, data_dir: Path) -> None:
        expected_payload = expected(data_dir)
        parser = PageParser(screen="entitlements", table="feature-entitlements")
        parser.feed(render("/entitlements", data_dir))
        rows = expected_payload["entitlement_rows"]
        self.assertTrue(parser.screen_seen)
        self.assertTrue(parser.table_seen)
        self.assertEqual(" ".join(parser.h1), "Entitlements")
        self.assertIn(("Entitlements", "/entitlements"), parser.nav_links)
        self.assertEqual(
            parser.metrics,
            {key: str(value) for key, value in expected_payload["entitlement_metrics"].items()},
        )
        expected_order = [(str(row["workspace_id"]), str(row["feature"])) for row in rows]
        self.assertEqual(parser.row_order, expected_order)
        for row in rows:
            key = (str(row["workspace_id"]), str(row["feature"]))
            self.assertEqual(set(parser.rows[key]), ENTITLEMENT_FIELDS)
            for field in ENTITLEMENT_FIELDS:
                self.assertEqual(parser.rows[key][field], str(row[field]), (key, field))

    def assert_overrides(self, data_dir: Path) -> None:
        expected_payload = expected(data_dir)
        parser = PageParser(screen="entitlement-overrides", table="entitlement-overrides")
        parser.feed(render("/entitlements/overrides", data_dir))
        rows = expected_payload["override_rows"]
        self.assertTrue(parser.screen_seen)
        self.assertTrue(parser.table_seen)
        self.assertEqual(" ".join(parser.h1), "Entitlement Overrides")
        self.assertEqual(
            parser.metrics,
            {key: str(value) for key, value in expected_payload["override_metrics"].items()},
        )
        expected_order = [(str(row["workspace_id"]), str(row["feature"])) for row in rows]
        self.assertEqual(parser.row_order, expected_order)
        for row in rows:
            key = (str(row["workspace_id"]), str(row["feature"]))
            self.assertEqual(set(parser.rows[key]), OVERRIDE_FIELDS)
            for field in OVERRIDE_FIELDS:
                self.assertEqual(parser.rows[key][field], str(row[field]), (key, field))

    def test_source_structure_and_unittest_regression(self) -> None:
        self.assertTrue(Path("/app/workspace_app/screens/entitlements.py").exists())
        self.assertTrue(Path("/app/workspace_app/screens/entitlement_overrides.py").exists())
        self.assertTrue(Path("/app/workspace_app/selectors/entitlements.py").exists())
        combined_tests = "\n".join(path.read_text() for path in Path("/app/tests").glob("test*.py"))
        self.assertIn("/entitlements", combined_tests)
        self.assertIn("/entitlements/overrides", combined_tests)
        self.assertIn("Entitlement Overrides", combined_tests)
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
                self.assertIn('href="/entitlements"', html)
                self.assertIn("Entitlements", html)

    def test_visible_fixture_exact(self) -> None:
        data_dir = Path("/app/fixtures/visible")
        self.assert_entitlements(data_dir)
        self.assert_overrides(data_dir)

    def test_hidden_fixtures_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for variant in ["hidden-a", "hidden-b"]:
                data_dir = write_fixture(root, variant=variant)
                self.assert_entitlements(data_dir)
                self.assert_overrides(data_dir)


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

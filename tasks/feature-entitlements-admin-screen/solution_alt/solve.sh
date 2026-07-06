#!/usr/bin/env bash
set -euo pipefail

cat > workspace_app/selectors/entitlements.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from workspace_app.data import load_json


ORDER = {"blocked": 0, "over_limit": 1, "override_review": 2, "ok": 3}


def _load(data_dir: str | Path) -> tuple[list[dict], dict, dict, dict, dict, date]:
    workspaces = load_json(data_dir, "workspaces.json")
    subscription_doc = load_json(data_dir, "subscriptions.json")
    plans = load_json(data_dir, "plan_features.json")
    report_date = date.fromisoformat(subscription_doc["report_date"])
    subscriptions = {row["workspace_id"]: row for row in subscription_doc["subscriptions"]}
    usage = defaultdict(int)
    for row in load_json(data_dir, "usage.json"):
        usage[(row["workspace_id"], row["feature"])] = int(row["current_usage"])
    overrides = {}
    for row in load_json(data_dir, "overrides.json"):
        expires = date.fromisoformat(row["expires_on"])
        if expires < report_date:
            continue
        key = (row["workspace_id"], row["feature"])
        if key not in overrides or row["expires_on"] > overrides[key]["expires_on"]:
            overrides[key] = row
    return workspaces, subscriptions, plans, usage, overrides, report_date


def entitlement_data(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int], list[dict[str, object]], dict[str, int]]:
    workspaces, subscriptions, plans, usage, overrides, report_date = _load(data_dir)
    expired_count = sum(
        1
        for row in load_json(data_dir, "overrides.json")
        if date.fromisoformat(row["expires_on"]) < report_date
    )
    workspace_by_id = {row["workspace_id"]: row for row in workspaces}
    features = sorted({name for features_by_plan in plans.values() for name in features_by_plan})
    rows: list[dict[str, object]] = []
    for workspace in workspaces:
        workspace_id = workspace["workspace_id"]
        plan_name = workspace["plan"]
        serviceable = subscriptions[workspace_id]["status"] in ("active", "trialing")
        for feature in features:
            spec = plans[plan_name][feature]
            override = overrides.get((workspace_id, feature))
            enabled = bool(spec["enabled"] if override is None else override["enabled"])
            days = "" if override is None else (date.fromisoformat(override["expires_on"]) - report_date).days
            limit = spec["limit"]
            current_usage = usage[(workspace_id, feature)]
            reasons: list[str] = []
            if not serviceable:
                reasons.append("subscription_not_serviceable")
            if not enabled:
                reasons.append("feature_disabled")
            if limit is not None and current_usage > int(limit):
                reasons.append("usage_over_limit")
            if override is not None and int(days) <= 14:
                reasons.append("override_expiring")
            if not serviceable:
                status, action = "blocked", "Restore subscription"
            elif not enabled:
                status, action = "blocked", "Review feature access"
            elif limit is not None and current_usage > int(limit):
                status, action = "over_limit", "Contact owner about limit"
            elif override is not None and int(days) <= 14:
                status, action = "override_review", "Review temporary override"
            else:
                status, action = "ok", "Monitor"
            rows.append(
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
                    "override_days_remaining": days,
                    "reason_codes": ",".join(reasons) if reasons else "none",
                    "recommended_action": action,
                }
            )
    rows.sort(key=lambda row: (ORDER[row["status"]], row["owner"], row["workspace"], row["feature"]))
    metrics = {
        "workspaces": len(workspaces),
        "blocked": len([row for row in rows if row["status"] == "blocked"]),
        "over-limit": len([row for row in rows if row["status"] == "over_limit"]),
        "overrides-expiring": len([row for row in rows if row["status"] == "override_review"]),
    }
    override_rows: list[dict[str, object]] = []
    for (workspace_id, feature), override in overrides.items():
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
    override_rows.sort(key=lambda row: (row["days_remaining"], row["owner"], row["workspace"], row["feature"]))
    override_metrics = {
        "active-overrides": len(override_rows),
        "expiring-overrides": len([row for row in override_rows if row["status"] == "expiring"]),
        "expired-overrides": expired_count,
    }
    return rows, metrics, override_rows, override_metrics


def entitlement_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    rows, metrics, _, _ = entitlement_data(data_dir)
    return rows, metrics


def override_rows(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    _, _, rows, metrics = entitlement_data(data_dir)
    return rows, metrics
PY

cat > workspace_app/screens/entitlements.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.entitlements import entitlement_rows


COLUMNS = [
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
]


def render(data_dir: Path) -> str:
    rows, metrics = entitlement_rows(data_dir)
    metric_html = "".join(
        '<div data-metric="%s">%s</div>' % (escape(key), escape(str(metrics[key])))
        for key in ["workspaces", "blocked", "over-limit", "overrides-expiring"]
    )
    headers = "".join("<th>%s</th>" % escape(column) for column in COLUMNS)
    body_rows = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(column), escape(str(row[column])))
            for column in COLUMNS
        )
        body_rows.append(
            '<tr data-workspace-id="%s" data-feature="%s">%s</tr>'
            % (escape(str(row["workspace_id"])), escape(str(row["feature"])), cells)
        )
    table = '<table data-table="feature-entitlements"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body_rows),
    )
    body = "<h1>Entitlements</h1><section>%s</section>%s" % (metric_html, table)
    return render_layout("Entitlements", "/entitlements", body, data_screen="entitlements")
PY

cat > workspace_app/screens/entitlement_overrides.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.entitlements import override_rows


COLUMNS = ["workspace", "owner", "feature", "enabled", "days_remaining", "status", "reason"]


def render(data_dir: Path) -> str:
    rows, metrics = override_rows(data_dir)
    metric_html = "".join(
        '<div data-metric="%s">%s</div>' % (escape(key), escape(str(metrics[key])))
        for key in ["active-overrides", "expiring-overrides", "expired-overrides"]
    )
    headers = "".join("<th>%s</th>" % escape(column) for column in COLUMNS)
    body_rows = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(column), escape(str(row[column])))
            for column in COLUMNS
        )
        body_rows.append(
            '<tr data-workspace-id="%s" data-feature="%s">%s</tr>'
            % (escape(str(row["workspace_id"])), escape(str(row["feature"])), cells)
        )
    table = '<table data-table="entitlement-overrides"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        headers,
        "".join(body_rows),
    )
    body = "<h1>Entitlement Overrides</h1><section>%s</section>%s" % (metric_html, table)
    return render_layout("Entitlement Overrides", "/entitlements/overrides", body, data_screen="entitlement-overrides")
PY

python - <<'PY'
from pathlib import Path

routing = Path("workspace_app/routing.py")
source = routing.read_text()
if "entitlements" not in source:
    source = source.replace(
        "from .screens import accounts, billing, home, reports, support",
        "from .screens import accounts, billing, entitlement_overrides, entitlements, home, reports, support",
    )
if '"/entitlements"' not in source:
    source = source.replace('    "/reports": reports.render,\n}', '    "/reports": reports.render,\n    "/entitlements": entitlements.render,\n}')
if '"/entitlements/overrides"' not in source:
    source = source.replace('    "/entitlements": entitlements.render,\n}', '    "/entitlements": entitlements.render,\n    "/entitlements/overrides": entitlement_overrides.render,\n}')
routing.write_text(source)

nav = Path("workspace_app/nav.py")
source = nav.read_text()
if "/entitlements" not in source:
    source = source.replace(
        ']\n',
        '    {"label": "Entitlements", "href": "/entitlements"},\n]\n',
    )
nav.write_text(source)
PY

cat > tests/test_entitlements.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class EntitlementsScreenTests(unittest.TestCase):
    def test_route_contract_and_visible_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.html"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "workspace_app.cli",
                    "--route",
                    "/entitlements",
                    "--data-dir",
                    "/app/fixtures/visible",
                    "--output",
                    str(output),
                ],
                check=True,
            )
            html = output.read_text()
        self.assertIn('<main data-screen="entitlements">', html)
        self.assertIn("<h1>Entitlements</h1>", html)
        self.assertIn('data-table="feature-entitlements"', html)
        self.assertIn('data-metric="blocked"', html)
        self.assertIn("Review temporary override", html)
        self.assertIn("Restore subscription", html)
        self.assertIn("reason_codes", html)

    def test_overrides_route_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "overrides.html"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "workspace_app.cli",
                    "--route",
                    "/entitlements/overrides",
                    "--data-dir",
                    "/app/fixtures/visible",
                    "--output",
                    str(output),
                ],
                check=True,
            )
            html = output.read_text()
        self.assertIn('<main data-screen="entitlement-overrides">', html)
        self.assertIn("<h1>Entitlement Overrides</h1>", html)
        self.assertIn('data-table="entitlement-overrides"', html)
        self.assertIn('data-metric="active-overrides"', html)


if __name__ == "__main__":
    unittest.main()
PY

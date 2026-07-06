#!/usr/bin/env bash
set -euo pipefail

cat > workspace_app/selectors/entitlements.py <<'PY'
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from workspace_app.data import load_json


STATUS_ORDER = {"blocked": 0, "over_limit": 1, "override_review": 2, "ok": 3}


def _active_overrides(overrides: list[dict[str, Any]], report_date: date) -> dict[tuple[str, str], dict[str, Any]]:
    active: dict[tuple[str, str], dict[str, Any]] = {}
    for override in overrides:
        expires = date.fromisoformat(str(override["expires_on"]))
        if expires < report_date:
            continue
        key = (str(override["workspace_id"]), str(override["feature"]))
        current = active.get(key)
        if current is None or str(override["expires_on"]) > str(current["expires_on"]):
            active[key] = override
    return active


def entitlement_data(data_dir: str | Path) -> tuple[list[dict[str, object]], dict[str, int], list[dict[str, object]], dict[str, int]]:
    workspaces = load_json(data_dir, "workspaces.json")
    subscriptions_doc = load_json(data_dir, "subscriptions.json")
    plans = load_json(data_dir, "plan_features.json")
    usage_rows = load_json(data_dir, "usage.json")
    overrides = load_json(data_dir, "overrides.json")
    report_date = date.fromisoformat(str(subscriptions_doc["report_date"]))
    subscriptions = {str(row["workspace_id"]): row for row in subscriptions_doc["subscriptions"]}
    usage = {
        (str(row["workspace_id"]), str(row["feature"])): int(row["current_usage"])
        for row in usage_rows
    }
    active_overrides = _active_overrides(overrides, report_date)
    features = sorted({feature for plan in plans.values() for feature in plan})
    expired_count = sum(
        1 for override in overrides if date.fromisoformat(str(override["expires_on"])) < report_date
    )
    workspace_by_id = {str(row["workspace_id"]): row for row in workspaces}

    rows: list[dict[str, object]] = []
    for workspace in workspaces:
        workspace_id = str(workspace["workspace_id"])
        plan_name = str(workspace["plan"])
        subscription = subscriptions[workspace_id]
        serviceable = subscription["status"] in {"active", "trialing"}
        for feature in features:
            spec = plans[plan_name][feature]
            override = active_overrides.get((workspace_id, feature))
            enabled = bool(spec["enabled"])
            override_days: int | str = ""
            if override is not None:
                enabled = bool(override["enabled"])
                override_days = (date.fromisoformat(str(override["expires_on"])) - report_date).days
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
                    "override_days_remaining": override_days,
                    "reason_codes": ",".join(reasons) if reasons else "none",
                    "recommended_action": action,
                }
            )
    rows.sort(
        key=lambda row: (
            STATUS_ORDER[str(row["status"])],
            str(row["owner"]),
            str(row["workspace"]),
            str(row["feature"]),
        )
    )
    metrics = {
        "workspaces": len(workspaces),
        "blocked": sum(row["status"] == "blocked" for row in rows),
        "over-limit": sum(row["status"] == "over_limit" for row in rows),
        "overrides-expiring": sum(row["status"] == "override_review" for row in rows),
    }
    override_rows: list[dict[str, object]] = []
    for (workspace_id, feature), override in active_overrides.items():
        workspace = workspace_by_id[workspace_id]
        days = (date.fromisoformat(str(override["expires_on"])) - report_date).days
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


METRICS = ["workspaces", "blocked", "over-limit", "overrides-expiring"]
FIELDS = [
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


def _metrics(metrics: dict[str, int]) -> str:
    return '<section class="metrics">%s</section>' % "".join(
        '<span data-metric="%s">%s</span>' % (escape(key), escape(str(metrics[key])))
        for key in METRICS
    )


def _table(rows: list[dict[str, object]]) -> str:
    header = "".join("<th>%s</th>" % escape(field.replace("_", " ").title()) for field in FIELDS)
    body = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field in FIELDS
        )
        body.append(
            '<tr data-workspace-id="%s" data-feature="%s">%s</tr>'
            % (escape(str(row["workspace_id"])), escape(str(row["feature"])), cells)
        )
    return '<table data-table="feature-entitlements"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        header,
        "".join(body),
    )


def render(data_dir: Path) -> str:
    rows, metrics = entitlement_rows(data_dir)
    body = "<h1>Entitlements</h1>%s%s" % (_metrics(metrics), _table(rows))
    return render_layout("Entitlements", "/entitlements", body, data_screen="entitlements")
PY

cat > workspace_app/screens/entitlement_overrides.py <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path

from workspace_app.layout import render_layout
from workspace_app.selectors.entitlements import override_rows


METRICS = ["active-overrides", "expiring-overrides", "expired-overrides"]
FIELDS = ["workspace", "owner", "feature", "enabled", "days_remaining", "status", "reason"]


def render(data_dir: Path) -> str:
    rows, metrics = override_rows(data_dir)
    metric_html = "".join(
        '<span data-metric="%s">%s</span>' % (escape(key), escape(str(metrics[key])))
        for key in METRICS
    )
    header = "".join("<th>%s</th>" % escape(field.replace("_", " ").title()) for field in FIELDS)
    body_rows = []
    for row in rows:
        cells = "".join(
            '<td data-field="%s">%s</td>' % (escape(field), escape(str(row[field])))
            for field in FIELDS
        )
        body_rows.append(
            '<tr data-workspace-id="%s" data-feature="%s">%s</tr>'
            % (escape(str(row["workspace_id"])), escape(str(row["feature"])), cells)
        )
    table = '<table data-table="entitlement-overrides"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        header,
        "".join(body_rows),
    )
    body = "<h1>Entitlement Overrides</h1><section>%s</section>%s" % (metric_html, table)
    return render_layout("Entitlement Overrides", "/entitlements/overrides", body, data_screen="entitlement-overrides")
PY

python - <<'PY'
from pathlib import Path

routing = Path("workspace_app/routing.py")
text = routing.read_text()
text = text.replace(
    "from .screens import accounts, billing, home, reports, support",
    "from .screens import accounts, billing, entitlement_overrides, entitlements, home, reports, support",
)
text = text.replace(
    '    "/reports": reports.render,\n}',
    '    "/reports": reports.render,\n    "/entitlements": entitlements.render,\n    "/entitlements/overrides": entitlement_overrides.render,\n}',
)
routing.write_text(text)

nav = Path("workspace_app/nav.py")
text = nav.read_text()
text = text.replace(
    '    {"label": "Reports", "href": "/reports"},\n]',
    '    {"label": "Reports", "href": "/reports"},\n    {"label": "Entitlements", "href": "/entitlements"},\n]',
)
nav.write_text(text)
PY

cat > tests/test_entitlements.py <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class EntitlementRouteTests(unittest.TestCase):
    def test_entitlements_route_renders_visible_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "entitlements.html"
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
        self.assertIn('data-screen="entitlements"', html)
        self.assertIn("<h1>Entitlements</h1>", html)
        self.assertIn('data-table="feature-entitlements"', html)
        self.assertIn('data-workspace-id="ws-100"', html)
        self.assertIn("Review feature access", html)
        self.assertIn("Contact owner about limit", html)
        self.assertIn("reason_codes", html)
        self.assertIn('href="/entitlements"', html)

    def test_override_route_renders_visible_fixture(self) -> None:
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
        self.assertIn('data-screen="entitlement-overrides"', html)
        self.assertIn("<h1>Entitlement Overrides</h1>", html)
        self.assertIn('data-table="entitlement-overrides"', html)
        self.assertIn('data-metric="expired-overrides"', html)


if __name__ == "__main__":
    unittest.main()
PY

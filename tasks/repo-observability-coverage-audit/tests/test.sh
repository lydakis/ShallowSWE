#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


APP = Path(os.environ.get("APP_DIR", "/app"))
OUTPUT_FILES = {
    "route_observability.json",
    "owner_gaps.csv",
    "observability_board.md",
    "remediation_plan.csv",
    "summary.json",
}
CONTROL_ORDER = [
    "request_started",
    "request_succeeded",
    "request_failed",
    "trace_context",
    "pii_safe",
    "dashboard_panel",
    "paging_alert",
    "runbook_current",
    "downstream_trace",
    "rollback_ready",
]
ACTION_BY_CONTROL = {
    "request_started": "add request_started telemetry",
    "request_succeeded": "add request_succeeded telemetry",
    "request_failed": "add request_failed telemetry",
    "trace_context": "propagate trace_id in telemetry",
    "pii_safe": "remove PII fields from telemetry",
    "dashboard_panel": "add dashboard panel",
    "paging_alert": "add paging alert",
    "runbook_current": "refresh route runbook",
    "downstream_trace": "propagate trace_id to downstream service",
    "rollback_ready": "add rollback plan for recent deploy",
}
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".go"}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_alerts(root: Path) -> set[str]:
    route_ids: set[str] = set()
    for path in sorted((root / "alerts").glob("*.yaml")):
        current_route: str | None = None
        for raw_line in path.read_text().splitlines():
            line = raw_line.strip()
            if line.startswith("- route_id:"):
                current_route = line.split(":", 1)[1].strip()
            elif line.startswith("severity:") and current_route:
                severity = line.split(":", 1)[1].strip()
                if severity == "page":
                    route_ids.add(current_route)
                current_route = None
    return route_ids


def dashboard_routes(root: Path) -> set[str]:
    route_ids: set[str] = set()
    for path in sorted((root / "dashboards").glob("*.json")):
        data = json.loads(path.read_text())
        for panel in data.get("panels", []):
            route_id = panel.get("route_id")
            if route_id:
                route_ids.add(route_id)
    return route_ids


def source_evidence(root: Path, service_id: str, route_id: str) -> tuple[list[str], str]:
    evidence: list[str] = []
    chunks: list[str] = []
    service_root = root / "services" / service_id / "src"
    for path in sorted(service_root.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        text = path.read_text(errors="ignore")
        if route_id in text:
            evidence.append(path.relative_to(root).as_posix())
            chunks.extend(line for line in text.splitlines() if route_id in line)
    return evidence, "\n".join(chunks)


def active_exemptions(root: Path, report_date: str) -> dict[str, set[str]]:
    exemptions: dict[str, set[str]] = defaultdict(set)
    path = root / "exemptions" / "observability_exemptions.csv"
    if not path.exists():
        return exemptions
    for row in read_csv(path):
        if row["expires_on"] >= report_date:
            exemptions[row["route_id"]].add(row["control"])
    return exemptions


def open_incidents(root: Path) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    path = root / "incidents" / "incidents.csv"
    if not path.exists():
        return counts
    for row in read_csv(path):
        if row["status"] == "open" and row["severity"] in {"P0", "P1"}:
            counts[row["route_id"]] += 1
    return counts


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def route_edges(root: Path) -> dict[str, list[dict[str, str]]]:
    path = root / "dependencies" / "route_edges.csv"
    edges: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return edges
    for row in read_csv(path):
        edges[row["source_route_id"]].append(row)
    return edges


def runbooks(root: Path) -> dict[str, dict[str, str]]:
    path = root / "runbooks" / "route_runbooks.json"
    if not path.exists():
        return {}
    return {row["route_id"]: row for row in json.loads(path.read_text())}


def relevant_deploys(
    root: Path,
    *,
    report_date: date,
    deploy_recency_days: int,
) -> dict[str, list[dict[str, str]]]:
    path = root / "deployments" / "recent_deploys.csv"
    deploys: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return deploys
    cutoff = report_date - timedelta(days=deploy_recency_days)
    for row in read_csv(path):
        deployed_at = parse_date(row["deployed_at"])
        if deployed_at < cutoff or deployed_at > report_date:
            continue
        changed_routes = [part.strip() for part in row["changed_routes"].split(";") if part.strip()]
        for changed_route in changed_routes:
            deploys[f"{row['service_id']}:{changed_route}"].append(row)
    return deploys


def deploys_for_route(
    deploys: dict[str, list[dict[str, str]]],
    service_id: str,
    route_id: str,
) -> list[dict[str, str]]:
    rows = []
    rows.extend(deploys.get(f"{service_id}:{route_id}", []))
    rows.extend(deploys.get(f"{service_id}:*", []))
    return sorted(rows, key=lambda row: (row["deployed_at"], row["commit"]))


def expected_outputs(root: Path) -> dict[str, object]:
    services = {
        row["service_id"]: row
        for row in json.loads((root / "catalog" / "services.json").read_text())
    }
    routes = read_csv(root / "catalog" / "routes.csv")
    teams = read_csv(root / "owners" / "teams.csv")
    policies = json.loads((root / "policies" / "coverage_rules.json").read_text())
    report_date_text = policies["report_date"]
    report_date = parse_date(report_date_text)
    required_events = policies["required_events"]
    pii_tokens = policies["pii_tokens"]
    dashboard_required_tier = int(policies["dashboard_required_tier"])
    paging_alert_required_tier = int(policies["paging_alert_required_tier"])
    runbook_required_tier = int(policies["runbook_required_tier"])
    runbook_review_days = int(policies["runbook_review_days"])
    trace_edge_required_tier = int(policies["trace_edge_required_tier"])
    deploy_recency_days = int(policies["deploy_recency_days"])
    due_days = {key: int(value) for key, value in policies["due_days"].items()}
    dashboards = dashboard_routes(root)
    paging_alerts = parse_alerts(root)
    exemptions = active_exemptions(root, report_date_text)
    incidents = open_incidents(root)
    edges_by_route = route_edges(root)
    runbook_by_route = runbooks(root)
    deploys_by_route = relevant_deploys(
        root,
        report_date=report_date,
        deploy_recency_days=deploy_recency_days,
    )

    route_rows: list[dict[str, object]] = []
    remediation_rows: list[dict[str, object]] = []
    for route in sorted(routes, key=lambda row: row["route_id"]):
        service = services[route["service_id"]]
        tier = int(route["tier_override"] or service["tier"])
        evidence_files, evidence_text = source_evidence(root, route["service_id"], route["route_id"])
        missing_events = [event for event in required_events if event not in evidence_text]
        pii_expected = route["pii_expected"].lower() == "true"
        pii_leaks = [] if pii_expected else sorted(token for token in pii_tokens if token in evidence_text)
        has_dashboard = route["route_id"] in dashboards
        has_paging_alert = route["route_id"] in paging_alerts
        required_runbook = tier <= runbook_required_tier
        runbook = runbook_by_route.get(route["route_id"])
        if not required_runbook:
            runbook_status = "not_required"
        elif not runbook:
            runbook_status = "missing"
        elif parse_date(runbook["reviewed_on"]) < report_date - timedelta(days=runbook_review_days):
            runbook_status = "stale"
        else:
            runbook_status = "current"
        trace_edge_gaps = []
        for edge in edges_by_route.get(route["route_id"], []):
            if edge["critical"].lower() != "true" or tier > trace_edge_required_tier:
                continue
            if edge["target_service_id"] not in evidence_text or "downstream_trace_id" not in evidence_text:
                trace_edge_gaps.append(edge["target_service_id"])
        trace_edge_gaps = sorted(set(trace_edge_gaps))
        route_deploys = deploys_for_route(deploys_by_route, route["service_id"], route["route_id"])
        rollback_ready = not any(row["rollback_ready"].lower() == "false" for row in route_deploys)

        raw_missing: list[str] = []
        raw_missing.extend(missing_events)
        if "trace_id" not in evidence_text:
            raw_missing.append("trace_context")
        if pii_leaks:
            raw_missing.append("pii_safe")
        if tier <= dashboard_required_tier and not has_dashboard:
            raw_missing.append("dashboard_panel")
        if tier <= paging_alert_required_tier and not has_paging_alert:
            raw_missing.append("paging_alert")
        if runbook_status in {"missing", "stale"}:
            raw_missing.append("runbook_current")
        if trace_edge_gaps:
            raw_missing.append("downstream_trace")
        if not rollback_ready:
            raw_missing.append("rollback_ready")
        raw_missing = [control for control in CONTROL_ORDER if control in raw_missing]

        active = exemptions.get(route["route_id"], set())
        exempted = [
            control
            for control in raw_missing
            if control in active and control != "pii_safe"
        ]
        missing_controls = [control for control in raw_missing if control not in set(exempted)]
        open_count = incidents.get(route["route_id"], 0)
        if (
            open_count > 0
            or "pii_safe" in missing_controls
            or (tier == 1 and "paging_alert" in missing_controls)
            or ("rollback_ready" in missing_controls and route_deploys)
        ):
            status = "blocked"
        elif raw_missing and not missing_controls:
            status = "accepted_risk"
        elif missing_controls:
            status = "needs_work"
        else:
            status = "ready"

        route_rows.append(
            {
                "route_id": route["route_id"],
                "service_id": route["service_id"],
                "method": route["method"],
                "path": route["path"],
                "team": service["team"],
                "tier": tier,
                "status": status,
                "missing_controls": missing_controls,
                "exempted_controls": exempted,
                "missing_events": missing_events,
                "has_dashboard": has_dashboard,
                "has_paging_alert": has_paging_alert,
                "evidence_files": evidence_files,
                "open_incidents": open_count,
                "pii_leaks": pii_leaks,
                "runbook_status": runbook_status,
                "trace_edge_gaps": trace_edge_gaps,
                "recent_deploys": len(route_deploys),
                "rollback_ready": rollback_ready,
            }
        )
        if status != "ready":
            if status == "blocked" and (
                open_count > 0 or "pii_safe" in missing_controls or (
                    tier == 1 and "paging_alert" in missing_controls
                )
            ):
                priority = "P0"
            elif status == "blocked":
                priority = "P1"
            elif status == "needs_work":
                priority = "P2"
            else:
                priority = "P3"
            actions: list[str] = []
            if open_count > 0:
                actions.append("resolve open incident")
            actions.extend(ACTION_BY_CONTROL[control] for control in missing_controls)
            if not actions:
                actions.append("monitor accepted exemption")
            evidence = []
            evidence.extend(sorted(evidence_files))
            evidence.extend(sorted(f"deploy:{row['commit']}" for row in route_deploys))
            if runbook:
                evidence.append(f"runbook:{runbook['url']}")
            remediation_rows.append(
                {
                    "route_id": route["route_id"],
                    "team": service["team"],
                    "priority": priority,
                    "due_date": (report_date + timedelta(days=due_days[status])).isoformat(),
                    "actions": ";".join(actions),
                    "evidence": ";".join(evidence),
                }
            )

    by_team: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in route_rows:
        by_team[str(row["team"])].append(row)
    owner_rows: list[dict[str, object]] = []
    for team in sorted(teams, key=lambda row: row["team"]):
        owned = sorted(by_team.get(team["team"], []), key=lambda row: str(row["route_id"]))
        owner_rows.append(
            {
                "team": team["team"],
                "manager": team["manager"],
                "slack": team["slack"],
                "pagerduty": team["pagerduty"],
                "routes": ";".join(str(row["route_id"]) for row in owned),
                "ready": sum(1 for row in owned if row["status"] == "ready"),
                "needs_work": sum(1 for row in owned if row["status"] == "needs_work"),
                "blocked": sum(1 for row in owned if row["status"] == "blocked"),
                "accepted_risk": sum(1 for row in owned if row["status"] == "accepted_risk"),
                "missing_controls": sum(len(row["missing_controls"]) for row in owned),
                "open_incidents": sum(int(row["open_incidents"]) for row in owned),
                "runbook_gaps": sum(1 for row in owned if "runbook_current" in row["missing_controls"]),
                "trace_edge_gaps": sum(1 for row in owned if "downstream_trace" in row["missing_controls"]),
                "rollback_gaps": sum(1 for row in owned if "rollback_ready" in row["missing_controls"]),
                "highest_tier": min((int(row["tier"]) for row in owned), default=""),
            }
        )

    board_sections = [
        ("Blocked", "blocked"),
        ("Needs Work", "needs_work"),
        ("Accepted Risk", "accepted_risk"),
        ("Ready", "ready"),
    ]
    lines = ["# Observability Coverage Board", ""]
    for title, status in board_sections:
        lines.append(f"## {title}")
        rows = [row for row in route_rows if row["status"] == status]
        if rows:
            for row in rows:
                missing = ";".join(row["missing_controls"]) or "none"
                if row["missing_controls"]:
                    action = ACTION_BY_CONTROL[row["missing_controls"][0]]
                elif int(row["open_incidents"]) > 0:
                    action = "resolve open incident"
                else:
                    action = "monitor"
                lines.append(
                    f"- {row['route_id']} [{row['team']}] missing={missing} action={action}"
                )
        else:
            lines.append("- none")
        lines.append("")
    board = "\n".join(lines).rstrip() + "\n"

    summary = {
        "routes": len(route_rows),
        "ready": sum(1 for row in route_rows if row["status"] == "ready"),
        "needs_work": sum(1 for row in route_rows if row["status"] == "needs_work"),
        "blocked": sum(1 for row in route_rows if row["status"] == "blocked"),
        "accepted_risk": sum(1 for row in route_rows if row["status"] == "accepted_risk"),
        "services": len(services),
        "teams": len(teams),
        "missing_controls": sum(len(row["missing_controls"]) for row in route_rows),
        "open_incidents": sum(int(row["open_incidents"]) for row in route_rows),
        "tier1_blocked": sum(
            1 for row in route_rows if int(row["tier"]) == 1 and row["status"] == "blocked"
        ),
        "dashboard_gaps": sum(1 for row in route_rows if "dashboard_panel" in row["missing_controls"]),
        "paging_alert_gaps": sum(1 for row in route_rows if "paging_alert" in row["missing_controls"]),
        "runbook_gaps": sum(1 for row in route_rows if "runbook_current" in row["missing_controls"]),
        "trace_edge_gaps": sum(1 for row in route_rows if "downstream_trace" in row["missing_controls"]),
        "rollback_gaps": sum(1 for row in route_rows if "rollback_ready" in row["missing_controls"]),
        "recent_deploys": sum(int(row["recent_deploys"]) for row in route_rows),
    }
    remediation_rows = sorted(remediation_rows, key=lambda row: (row["priority"], row["route_id"]))

    return {
        "route_observability.json": {"routes": route_rows},
        "owner_gaps.csv": owner_rows,
        "observability_board.md": board,
        "remediation_plan.csv": remediation_rows,
        "summary.json": summary,
    }


def seed_hidden(root: Path) -> None:
    write_json(
        root / "catalog/services.json",
        [
            {"service_id": "admin", "display_name": "Admin", "team": "platform", "tier": 1, "language": "python"},
            {"service_id": "emails", "display_name": "Emails", "team": "growth", "tier": 3, "language": "typescript"},
            {"service_id": "orders", "display_name": "Orders", "team": "commerce", "tier": 1, "language": "python"},
            {"service_id": "risk", "display_name": "Risk", "team": "trust", "tier": 2, "language": "go"},
        ],
    )
    write_csv(
        root / "catalog/routes.csv",
        [
            {"route_id": "admin.audit", "service_id": "admin", "method": "GET", "path": "/admin/audit", "handler": "audit", "tier_override": "", "pii_expected": "false"},
            {"route_id": "emails.send", "service_id": "emails", "method": "POST", "path": "/emails/send", "handler": "sendEmail", "tier_override": "", "pii_expected": "true"},
            {"route_id": "orders.cancel", "service_id": "orders", "method": "POST", "path": "/orders/cancel", "handler": "cancel", "tier_override": "2", "pii_expected": "false"},
            {"route_id": "orders.place", "service_id": "orders", "method": "POST", "path": "/orders", "handler": "place", "tier_override": "", "pii_expected": "false"},
            {"route_id": "risk.score", "service_id": "risk", "method": "POST", "path": "/risk/score", "handler": "Score", "tier_override": "", "pii_expected": "false"},
        ],
        ["route_id", "service_id", "method", "path", "handler", "tier_override", "pii_expected"],
    )
    write_csv(
        root / "owners/teams.csv",
        [
            {"team": "commerce", "manager": "Case Vale", "slack": "#commerce", "pagerduty": "pd-commerce"},
            {"team": "growth", "manager": "Gwen Li", "slack": "#growth", "pagerduty": "pd-growth"},
            {"team": "platform", "manager": "Paz Ray", "slack": "#platform", "pagerduty": "pd-platform"},
            {"team": "trust", "manager": "Taj Noor", "slack": "#trust", "pagerduty": "pd-trust"},
        ],
        ["team", "manager", "slack", "pagerduty"],
    )
    write_json(
        root / "policies/coverage_rules.json",
        {
            "report_date": "2026-10-05",
            "required_events": ["request_started", "request_succeeded", "request_failed"],
            "dashboard_required_tier": 2,
            "paging_alert_required_tier": 2,
            "pii_tokens": ["email", "ssn", "card_number"],
            "runbook_required_tier": 2,
            "runbook_review_days": 60,
            "trace_edge_required_tier": 2,
            "deploy_recency_days": 10,
            "due_days": {
                "blocked": 2,
                "needs_work": 8,
                "accepted_risk": 15,
                "ready": 30,
            },
        },
    )
    write_csv(
        root / "dependencies/route_edges.csv",
        [
            {"source_route_id": "orders.place", "target_service_id": "risk", "critical": "true"},
            {"source_route_id": "orders.cancel", "target_service_id": "risk", "critical": "true"},
            {"source_route_id": "emails.send", "target_service_id": "orders", "critical": "true"},
            {"source_route_id": "admin.audit", "target_service_id": "risk", "critical": "false"},
        ],
        ["source_route_id", "target_service_id", "critical"],
    )
    write_json(
        root / "runbooks/route_runbooks.json",
        [
            {"route_id": "admin.audit", "url": "runbooks/admin-audit.md", "reviewed_on": "2026-09-15"},
            {"route_id": "orders.cancel", "url": "runbooks/orders-cancel.md", "reviewed_on": "2026-06-01"},
            {"route_id": "orders.place", "url": "runbooks/orders-place.md", "reviewed_on": "2026-10-01"},
            {"route_id": "risk.score", "url": "runbooks/risk-score.md", "reviewed_on": "2026-08-01"},
        ],
    )
    write_csv(
        root / "deployments/recent_deploys.csv",
        [
            {"service_id": "orders", "deployed_at": "2026-10-01", "commit": "bead001", "changed_routes": "orders.place;orders.cancel", "rollback_ready": "false"},
            {"service_id": "emails", "deployed_at": "2026-10-02", "commit": "bead002", "changed_routes": "*", "rollback_ready": "true"},
            {"service_id": "risk", "deployed_at": "2026-09-10", "commit": "bead003", "changed_routes": "risk.score", "rollback_ready": "false"},
        ],
        ["service_id", "deployed_at", "commit", "changed_routes", "rollback_ready"],
    )
    write_csv(
        root / "incidents/incidents.csv",
        [
            {"route_id": "risk.score", "date": "2026-10-04", "severity": "P1", "status": "open"},
            {"route_id": "orders.place", "date": "2026-10-03", "severity": "P2", "status": "open"},
        ],
        ["route_id", "date", "severity", "status"],
    )
    write_csv(
        root / "exemptions/observability_exemptions.csv",
        [
            {"route_id": "emails.send", "control": "request_failed", "expires_on": "2026-11-01", "reason": "esp migration"},
            {"route_id": "orders.cancel", "control": "dashboard_panel", "expires_on": "2026-09-01", "reason": "old dashboard"},
        ],
        ["route_id", "control", "expires_on", "reason"],
    )
    write_json(
        root / "dashboards/main.json",
        {
            "panels": [
                {"title": "Admin audit", "route_id": "admin.audit"},
                {"title": "Order placements", "route_id": "orders.place"},
                {"title": "Risk score", "route_id": "risk.score"},
            ]
        },
    )
    write(
        root / "alerts/routes.yaml",
        """
        alerts:
          - route_id: admin.audit
            severity: page
          - route_id: orders.cancel
            severity: ticket
          - route_id: risk.score
            severity: page
        """,
    )
    write(
        root / "services/admin/src/audit.py",
        """
        # route_id: admin.audit
        def audit(req):
            telemetry.track("request_started", {"route_id": "admin.audit", "trace_id": req.trace_id})
            telemetry.track("request_succeeded", {"route_id": "admin.audit", "trace_id": req.trace_id})
            telemetry.track("request_failed", {"route_id": "admin.audit", "trace_id": req.trace_id})
        """,
    )
    write(
        root / "services/orders/src/orders.py",
        """
        # route_id: orders.place
        def place(req):
            telemetry.track("request_started", {"route_id": "orders.place", "trace_id": req.trace_id})
            telemetry.track("request_succeeded", {"route_id": "orders.place", "trace_id": req.trace_id})
            telemetry.track("request_failed", {"route_id": "orders.place", "trace_id": req.trace_id})
            telemetry.track("downstream_call", {"route_id": "orders.place", "target_service_id": "risk", "downstream_trace_id": req.trace_id})

        # route_id: orders.cancel
        def cancel(req):
            telemetry.track("request_started", {"route_id": "orders.cancel"})
            telemetry.track("request_succeeded", {"route_id": "orders.cancel"})
        """,
    )
    write(
        root / "services/emails/src/send.ts",
        """
        // route_id: emails.send
        export function sendEmail(req) {
          telemetry.track("request_started", {route_id: "emails.send", trace_id: req.trace_id, email: req.email});
          telemetry.track("request_succeeded", {route_id: "emails.send", trace_id: req.trace_id});
        }
        """,
    )
    write(
        root / "services/risk/src/score.go",
        """
        // route_id: risk.score
        func Score(req Request) {
          telemetry.Track("request_started", map[string]string{"route_id": "risk.score", "trace_id": req.TraceID, "ssn": req.SSN})
          telemetry.Track("request_succeeded", map[string]string{"route_id": "risk.score", "trace_id": req.TraceID})
          telemetry.Track("request_failed", map[string]string{"route_id": "risk.score", "trace_id": req.TraceID})
        }
        """,
    )


def run_audit(script: Path, root: Path, output: Path, *, default_args: bool = False) -> None:
    if default_args:
        command = [sys.executable, str(script)]
        cwd = root
    else:
        command = [sys.executable, str(script), "--root", str(root), "--output", str(output)]
        cwd = root
    subprocess.run(command, cwd=cwd, text=True, check=True)


def read_output_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def assert_outputs(testcase: unittest.TestCase, root: Path, output: Path) -> None:
    testcase.assertTrue(output.exists(), f"missing output directory {output}")
    testcase.assertEqual(
        {path.name for path in output.iterdir() if path.is_file()},
        OUTPUT_FILES,
    )
    expected = expected_outputs(root)
    testcase.assertEqual(
        json.loads((output / "route_observability.json").read_text()),
        expected["route_observability.json"],
    )
    testcase.assertEqual(
        read_output_csv(output / "owner_gaps.csv"),
        [
            {key: str(value) for key, value in row.items()}
            for row in expected["owner_gaps.csv"]
        ],
    )
    testcase.assertEqual(
        (output / "observability_board.md").read_text().rstrip() + "\n",
        str(expected["observability_board.md"]).rstrip() + "\n",
    )
    testcase.assertEqual(
        read_output_csv(output / "remediation_plan.csv"),
        [
            {key: str(value) for key, value in row.items()}
            for row in expected["remediation_plan.csv"]
        ],
    )
    testcase.assertEqual(
        json.loads((output / "summary.json").read_text()),
        expected["summary.json"],
    )


class ObservabilityAuditVerifier(unittest.TestCase):
    def test_visible_default_run(self) -> None:
        script = APP / "scripts" / "build_observability_audit.py"
        self.assertTrue(script.exists(), "missing scripts/build_observability_audit.py")
        shutil.rmtree(APP / "output", ignore_errors=True)
        run_audit(script, APP, APP / "output", default_args=True)
        assert_outputs(self, APP, APP / "output")

    def test_hidden_repository_with_explicit_root_and_output(self) -> None:
        script = APP / "scripts" / "build_observability_audit.py"
        self.assertTrue(script.exists(), "missing scripts/build_observability_audit.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hidden-repo"
            seed_hidden(root)
            output = Path(tmp) / "hidden-output"
            run_audit(script, root, output)
            assert_outputs(self, root, output)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ObservabilityAuditVerifier)
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

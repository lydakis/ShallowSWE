#!/usr/bin/env bash
set -euo pipefail

mkdir -p scripts
cat > scripts/build_observability_audit.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import argparse
import csv
import json


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
OUTPUT_FILES = {
    "route_observability.json",
    "owner_gaps.csv",
    "observability_board.md",
    "remediation_plan.csv",
    "summary.json",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def dashboard_routes(root: Path) -> set[str]:
    route_ids: set[str] = set()
    for path in sorted((root / "dashboards").glob("*.json")):
        data = json.loads(path.read_text())
        for panel in data.get("panels", []):
            route_id = panel.get("route_id")
            if route_id:
                route_ids.add(route_id)
    return route_ids


def paging_alert_routes(root: Path) -> set[str]:
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


def source_evidence(root: Path, service_id: str, route_id: str) -> tuple[list[str], str]:
    service_root = root / "services" / service_id / "src"
    evidence_files: list[str] = []
    chunks: list[str] = []
    for path in sorted(service_root.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        text = path.read_text(errors="ignore")
        if route_id in text:
            evidence_files.append(path.relative_to(root).as_posix())
            chunks.extend(line for line in text.splitlines() if route_id in line)
    return evidence_files, "\n".join(chunks)


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


def build_rows(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
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
    paging_alerts = paging_alert_routes(root)
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
        exempted_controls = [
            control for control in raw_missing if control in active and control != "pii_safe"
        ]
        exempted_set = set(exempted_controls)
        missing_controls = [control for control in raw_missing if control not in exempted_set]
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
                "exempted_controls": exempted_controls,
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
    return route_rows, owner_rows, remediation_rows, summary


def board(route_rows: list[dict[str, object]]) -> str:
    lines = ["# Observability Coverage Board", ""]
    for title, status in [
        ("Blocked", "blocked"),
        ("Needs Work", "needs_work"),
        ("Accepted Risk", "accepted_risk"),
        ("Ready", "ready"),
    ]:
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
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else root / "output"
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file() and path.name not in OUTPUT_FILES:
            path.unlink()

    route_rows, owner_rows, remediation_rows, summary = build_rows(root)
    write_json(output / "route_observability.json", {"routes": route_rows})
    write_csv(
        output / "owner_gaps.csv",
        owner_rows,
        [
            "team",
            "manager",
            "slack",
            "pagerduty",
            "routes",
            "ready",
            "needs_work",
            "blocked",
            "accepted_risk",
            "missing_controls",
            "open_incidents",
            "runbook_gaps",
            "trace_edge_gaps",
            "rollback_gaps",
            "highest_tier",
        ],
    )
    (output / "observability_board.md").write_text(board(route_rows))
    write_csv(
        output / "remediation_plan.csv",
        remediation_rows,
        ["route_id", "team", "priority", "due_date", "actions", "evidence"],
    )
    write_json(output / "summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

python scripts/build_observability_audit.py

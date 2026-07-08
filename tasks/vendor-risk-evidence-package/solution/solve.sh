#!/usr/bin/env bash
set -euo pipefail

cd /app
mkdir -p scripts

cat > scripts/build_vendor_risk.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import argparse
import csv
import json


CONTROL_ACTIONS = {
    "dpa": "execute missing data protection addendum",
    "soc2_current": "collect current SOC 2 evidence",
    "pentest_current": "collect current penetration test",
    "subprocessor_approval": "approve or remove unapproved subprocessors",
    "regional_review": "review high-risk processing region",
    "production_source_reference": "add production integration source annotation",
    "open_incident": "close open vendor incident",
    "renewal_review": "complete renewal risk review",
    "accepted_exception": "review active risk exception",
}
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def source_evidence(root: Path, vendor_id: str) -> list[str]:
    base = root / "integrations"
    matches: list[str] = []
    if not base.exists():
        return matches
    for path in sorted(base.rglob("*")):
        if not path.is_file() or "/generated/" in path.as_posix():
            continue
        try:
            if vendor_id in path.read_text():
                matches.append(path.relative_to(root).as_posix())
        except UnicodeDecodeError:
            continue
    return sorted(matches)


def current_evidence(rows: list[dict[str, str]], report_date: date) -> set[str]:
    return {
        row["evidence_type"]
        for row in rows
        if row["status"] == "current" and parse_date(row["expires_on"]) >= report_date
    }


def active_exception_controls(rows: list[dict[str, str]], report_date: date) -> set[str]:
    return {row["control"] for row in rows if parse_date(row["expires_on"]) >= report_date}


def build(root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    policy = read_json(root / "policies/vendor_risk_policy.json")
    assert isinstance(policy, dict)
    report_date = parse_date(str(policy["report_date"]))
    vendors = read_csv(root / "inventory/vendors.csv")
    services = read_json(root / "inventory/services.json")
    assert isinstance(services, list)
    contracts = {row["contract_id"]: row for row in read_csv(root / "contracts/contracts.csv")}
    evidence_by_vendor: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(root / "security/evidence.csv"):
        evidence_by_vendor[row["vendor_id"]].append(row)
    subprocessors_by_vendor: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(root / "subprocessors/subprocessors.csv"):
        subprocessors_by_vendor[row["vendor_id"]].append(row)
    incidents_by_vendor: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(root / "incidents/vendor_incidents.csv"):
        incidents_by_vendor[row["vendor_id"]].append(row)
    exceptions_by_vendor: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(root / "exceptions/risk_exceptions.csv"):
        exceptions_by_vendor[row["vendor_id"]].append(row)
    services_by_vendor: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in services:
        assert isinstance(row, dict)
        services_by_vendor[str(row["vendor_id"])].append(row)

    dpa_classes = set(policy["dpa_required_data_classes"])
    regional_regions = set(policy["regional_review_regions"])
    regional_classes = set(policy["regional_review_data_classes"])
    action_order = list(policy["action_order"])
    required_by_criticality = policy["required_evidence_by_criticality"]
    renewal_window = int(policy["renewal_window_days"])

    vendor_rows: list[dict[str, object]] = []
    for vendor in vendors:
        vendor_id = vendor["vendor_id"]
        contract = contracts.get(vendor["contract_id"], {})
        required_evidence = list(required_by_criticality.get(vendor["criticality"], []))
        current = current_evidence(evidence_by_vendor[vendor_id], report_date)
        evidence_missing = [
            f"{kind}_current" for kind in required_evidence if kind not in current
        ]
        subs = subprocessors_by_vendor[vendor_id]
        subprocessor_gaps = sorted(
            row["subprocessor_id"] for row in subs if not truthy(row["approved"])
        )
        regional_gaps = sorted(
            row["subprocessor_id"]
            for row in subs
            if row["region"] in regional_regions and row["data_classification"] in regional_classes
        )
        source_files = source_evidence(root, vendor_id)
        vendor_services = sorted(str(row["service_id"]) for row in services_by_vendor[vendor_id])
        has_production_service = any(truthy(row.get("production")) for row in services_by_vendor[vendor_id])
        open_incidents = [
            row for row in incidents_by_vendor[vendor_id] if row["status"] == "open"
        ]
        renewal_due = 0 <= (parse_date(vendor["renewal_date"]) - report_date).days <= renewal_window

        raw_missing: list[str] = []
        if vendor["data_classification"] in dpa_classes and not truthy(contract.get("dpa_signed", "false")):
            raw_missing.append("dpa")
        raw_missing.extend(evidence_missing)
        if subprocessor_gaps:
            raw_missing.append("subprocessor_approval")
        if regional_gaps:
            raw_missing.append("regional_review")
        if has_production_service and not source_files:
            raw_missing.append("production_source_reference")
        if open_incidents:
            raw_missing.append("open_incident")
        if renewal_due:
            raw_missing.append("renewal_review")

        active_exceptions = active_exception_controls(exceptions_by_vendor[vendor_id], report_date)
        missing = [control for control in action_order if control in set(raw_missing) - active_exceptions]
        exempted = [control for control in action_order if control in set(raw_missing) & active_exceptions]
        if any(control in missing for control in ("dpa", "subprocessor_approval", "open_incident")):
            risk_status = "blocked"
        elif missing:
            risk_status = "needs_work"
        elif exempted:
            risk_status = "accepted_risk"
        else:
            risk_status = "ready"

        stale_or_missing = sorted(kind for kind in required_evidence if kind not in current)
        vendor_rows.append(
            {
                "vendor_id": vendor_id,
                "owner_team": vendor["owner_team"],
                "criticality": vendor["criticality"],
                "data_classification": vendor["data_classification"],
                "renewal_date": vendor["renewal_date"],
                "risk_status": risk_status,
                "missing_controls": missing,
                "exempted_controls": exempted,
                "contract_id": vendor["contract_id"],
                "services": vendor_services,
                "source_evidence_files": source_files,
                "current_evidence": sorted(current),
                "stale_or_missing_evidence": stale_or_missing,
                "subprocessor_gaps": subprocessor_gaps,
                "regional_gaps": regional_gaps,
                "open_incidents": len(open_incidents),
                "active_exceptions": sorted(active_exceptions),
            }
        )

    vendor_rows.sort(key=lambda row: str(row["vendor_id"]))
    (output / "vendor_risk.json").write_text(
        json.dumps({"vendors": vendor_rows}, indent=2, sort_keys=True) + "\n"
    )

    owner_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "vendors": 0,
            "blocked": 0,
            "needs_work": 0,
            "accepted_risk": 0,
            "ready": 0,
            "missing_controls": 0,
            "subprocessor_gaps": 0,
            "regional_gaps": 0,
            "open_incidents": 0,
            "renewals_due": 0,
        }
    )
    for row in vendor_rows:
        stats = owner_stats[str(row["owner_team"])]
        stats["vendors"] += 1
        stats[str(row["risk_status"])] += 1
        stats["missing_controls"] += len(row["missing_controls"])
        stats["subprocessor_gaps"] += len(row["subprocessor_gaps"])
        stats["regional_gaps"] += len(row["regional_gaps"])
        stats["open_incidents"] += int(row["open_incidents"])
        if "renewal_review" in row["missing_controls"] or "renewal_review" in row["exempted_controls"]:
            stats["renewals_due"] += 1
    owner_rows = [
        {"owner_team": owner, **stats}
        for owner, stats in sorted(owner_stats.items())
    ]
    write_csv(
        output / "owner_gaps.csv",
        [
            "owner_team",
            "vendors",
            "blocked",
            "needs_work",
            "accepted_risk",
            "ready",
            "missing_controls",
            "subprocessor_gaps",
            "regional_gaps",
            "open_incidents",
            "renewals_due",
        ],
        owner_rows,
    )

    due_days = policy["due_days"]
    plan_rows: list[dict[str, str]] = []
    vendors_by_id = {row["vendor_id"]: row for row in vendors}
    evidence_by_id = {row["vendor_id"]: row for row in vendor_rows}
    for row in vendor_rows:
        if row["risk_status"] == "ready":
            continue
        if row["risk_status"] == "blocked":
            priority = "P0"
        elif row["risk_status"] == "needs_work" and "open_incident" in row["missing_controls"]:
            priority = "P1"
        elif row["risk_status"] == "needs_work":
            priority = "P2"
        else:
            priority = "P3"
        due_date = report_date + timedelta(days=int(due_days[str(row["risk_status"])]))
        action_controls = list(row["missing_controls"])
        if row["exempted_controls"]:
            action_controls.append("accepted_exception")
        actions = [CONTROL_ACTIONS[control] for control in action_order if control in set(action_controls)]
        vendor_id = str(row["vendor_id"])
        current_evidence_types = sorted(row["current_evidence"])
        evidence_parts: list[str] = []
        evidence_parts.extend(row["source_evidence_files"])
        evidence_parts.extend(f"service:{service_id}" for service_id in row["services"])
        evidence_parts.append(f"contract:{row['contract_id']}")
        evidence_parts.extend(f"evidence:{kind}" for kind in current_evidence_types)
        evidence_parts.extend(f"subprocessor:{sub_id}" for sub_id in sorted(set(row["subprocessor_gaps"]) | set(row["regional_gaps"])))
        evidence_parts.extend(
            f"incident:{incident['severity']}"
            for incident in sorted(incidents_by_vendor[vendor_id], key=lambda item: item["severity"])
            if incident["status"] == "open"
        )
        evidence_parts.extend(f"exception:{control}" for control in row["active_exceptions"])
        plan_rows.append(
            {
                "vendor_id": vendor_id,
                "owner_team": str(row["owner_team"]),
                "priority": priority,
                "due_date": due_date.isoformat(),
                "actions": ";".join(actions),
                "evidence": ";".join(evidence_parts),
            }
        )
    plan_rows.sort(
        key=lambda row: (
            PRIORITY_RANK[row["priority"]],
            vendors_by_id[row["vendor_id"]]["renewal_date"],
            row["vendor_id"],
        )
    )
    write_csv(output / "renewal_actions.csv", ["vendor_id", "owner_team", "priority", "due_date", "actions", "evidence"], plan_rows)

    summary = {
        "vendors": len(vendor_rows),
        "owners": len(owner_stats),
        "blocked": sum(1 for row in vendor_rows if row["risk_status"] == "blocked"),
        "needs_work": sum(1 for row in vendor_rows if row["risk_status"] == "needs_work"),
        "accepted_risk": sum(1 for row in vendor_rows if row["risk_status"] == "accepted_risk"),
        "ready": sum(1 for row in vendor_rows if row["risk_status"] == "ready"),
        "missing_controls": sum(len(row["missing_controls"]) for row in vendor_rows),
        "subprocessor_gaps": sum(len(row["subprocessor_gaps"]) for row in vendor_rows),
        "regional_gaps": sum(len(row["regional_gaps"]) for row in vendor_rows),
        "open_incidents": sum(int(row["open_incidents"]) for row in vendor_rows),
        "renewals_due": sum(
            1
            for row in vendor_rows
            if "renewal_review" in row["missing_controls"] or "renewal_review" in row["exempted_controls"]
        ),
        "active_exceptions": sum(len(row["exempted_controls"]) for row in vendor_rows),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/app")
    parser.add_argument("--output", default="/app/output")
    args = parser.parse_args()
    build(Path(args.root), Path(args.output))


if __name__ == "__main__":
    main()
PY

python scripts/build_vendor_risk.py --root /app --output /app/output

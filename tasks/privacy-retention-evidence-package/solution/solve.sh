#!/usr/bin/env bash
set -euo pipefail

cd /app
mkdir -p scripts

cat > scripts/build_retention_audit.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import argparse
import csv
import json


CONTROL_ACTIONS = {
    "retention_limit": "reduce retention to policy limit",
    "purge_job": "add purge job for deletion mode",
    "purge_job_current": "repair stale or slow purge job",
    "subject_export": "repair subject export job",
    "downstream_delete": "propagate deletion to downstream datasets",
    "downstream_export": "propagate export to downstream datasets",
    "source_reference": "add source dataset annotation",
    "open_incident": "resolve open data incident",
    "legal_hold": "review active legal hold",
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


def truthy(value: str) -> bool:
    return value.strip().lower() == "true"


def is_current(report_date: date, value: str, max_age_days: int) -> bool:
    return (report_date - parse_date(value)).days <= max_age_days


def active_exemptions(rows: list[dict[str, str]], report_date: date) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if parse_date(row["expires_on"]) >= report_date:
            result[row["dataset_id"]].add(row["control"])
    return result


def active_holds(rows: list[dict[str, str]], report_date: date) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "active" and parse_date(row["expires_on"]) >= report_date:
            result[row["dataset_id"]].append(row)
    return result


def source_evidence(root: Path, dataset_id: str) -> list[str]:
    matches: list[str] = []
    for path in sorted((root / "services").rglob("*")):
        if not path.is_file() or "/generated/" in path.as_posix():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        if dataset_id in text:
            matches.append(path.relative_to(root).as_posix())
    return matches


def build(root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    policy = read_json(root / "policies/retention_policy.json")
    assert isinstance(policy, dict)
    report_date = parse_date(str(policy["report_date"]))
    action_order = list(policy["action_order"])
    expected_by_class = dict(policy["classification_retention_days"])
    stale_job_days = int(policy["stale_job_days"])
    export_stale_days = int(policy["export_job_stale_days"])
    propagation_required = set(policy["propagation_required_classifications"])
    due_days = {key: int(value) for key, value in dict(policy["due_days"]).items()}

    datasets = read_csv(root / "catalog/datasets.csv")
    purge_jobs = read_csv(root / "jobs/purge_jobs.csv")
    export_jobs = read_csv(root / "jobs/export_jobs.csv")
    incidents = read_csv(root / "incidents/data_incidents.csv")
    edges = read_csv(root / "lineage/downstream_edges.csv")
    holds = active_holds(read_csv(root / "legal/holds.csv"), report_date)
    exemptions = active_exemptions(read_csv(root / "exemptions/retention_exemptions.csv"), report_date)

    dataset_rows: list[dict[str, object]] = []
    hold_ids_by_dataset = {dataset: sorted(row["hold_id"] for row in rows) for dataset, rows in holds.items()}
    incident_rows = {
        dataset_id: sorted([row for row in incidents if row["dataset_id"] == dataset_id and row["status"] == "open"], key=lambda row: row["severity"])
        for dataset_id in {row["dataset_id"] for row in incidents}
    }

    for dataset in sorted(datasets, key=lambda row: row["dataset_id"]):
        dataset_id = dataset["dataset_id"]
        expected = int(expected_by_class[dataset["classification"]])
        configured = int(dataset["retention_days"])
        deletion_mode = dataset["deletion_mode"]
        matching_purge = sorted(
            [row for row in purge_jobs if row["dataset_id"] == dataset_id],
            key=lambda row: row["job_id"],
        )
        matching_mode_purge = [row for row in matching_purge if row["mode"] == deletion_mode]
        current_mode_purge = [
            row
            for row in matching_mode_purge
            if int(row["schedule_days"]) <= expected and is_current(report_date, row["last_success_at"], stale_job_days)
        ]
        matching_export = sorted(
            [row for row in export_jobs if row["dataset_id"] == dataset_id],
            key=lambda row: row["job_id"],
        )
        current_subject_export = [
            row
            for row in matching_export
            if row["scope"] == "subject" and is_current(report_date, row["last_success_at"], export_stale_days)
        ]
        dataset_edges = [row for row in edges if row["source_dataset_id"] == dataset_id]
        delete_gaps = sorted(
            row["target_dataset_id"]
            for row in dataset_edges
            if dataset["classification"] in propagation_required and not truthy(row["delete_propagates"])
        )
        export_gaps = sorted(
            row["target_dataset_id"]
            for row in dataset_edges
            if dataset["subject_type"] in {"customer", "prospect"} and not truthy(row["export_propagates"])
        )
        evidence_files = source_evidence(root, dataset_id)
        open_incidents = incident_rows.get(dataset_id, [])

        missing: list[str] = []
        if configured > expected:
            missing.append("retention_limit")
        if deletion_mode != "none":
            if not matching_mode_purge:
                missing.append("purge_job")
            elif not current_mode_purge:
                missing.append("purge_job_current")
        if dataset["subject_type"] in {"customer", "prospect"} and not current_subject_export:
            missing.append("subject_export")
        if delete_gaps:
            missing.append("downstream_delete")
        if export_gaps:
            missing.append("downstream_export")
        if not evidence_files:
            missing.append("source_reference")
        if open_incidents:
            missing.append("open_incident")

        exempted = sorted(control for control in missing if control in exemptions.get(dataset_id, set()))
        missing = [control for control in missing if control not in set(exempted)]

        if any(control in {"retention_limit", "purge_job", "downstream_delete", "open_incident"} for control in missing):
            status = "blocked"
        elif missing:
            status = "needs_work"
        elif dataset_id in holds:
            status = "accepted_risk"
        else:
            status = "ready"

        dataset_rows.append(
            {
                "dataset_id": dataset_id,
                "system_id": dataset["system_id"],
                "owner_team": dataset["owner_team"],
                "classification": dataset["classification"],
                "subject_type": dataset["subject_type"],
                "expected_retention_days": expected,
                "configured_retention_days": configured,
                "deletion_mode": deletion_mode,
                "status": status,
                "missing_controls": missing,
                "exempted_controls": exempted,
                "legal_hold_active": dataset_id in holds,
                "downstream_delete_gaps": delete_gaps,
                "downstream_export_gaps": export_gaps,
                "source_evidence_files": evidence_files,
                "purge_jobs": [row["job_id"] for row in matching_purge],
                "export_jobs": [row["job_id"] for row in matching_export],
                "open_incidents": len(open_incidents),
            }
        )

    (output / "dataset_retention.json").write_text(
        json.dumps({"datasets": dataset_rows}, indent=2, sort_keys=True) + "\n"
    )

    owner_stats: dict[str, dict[str, int]] = defaultdict(lambda: {
        "datasets": 0,
        "blocked": 0,
        "needs_work": 0,
        "accepted_risk": 0,
        "ready": 0,
        "missing_controls": 0,
        "downstream_gaps": 0,
        "open_incidents": 0,
        "legal_holds": 0,
    })
    for row in dataset_rows:
        stats = owner_stats[str(row["owner_team"])]
        stats["datasets"] += 1
        stats[str(row["status"])] += 1
        stats["missing_controls"] += len(row["missing_controls"])  # type: ignore[arg-type]
        stats["downstream_gaps"] += len(row["downstream_delete_gaps"]) + len(row["downstream_export_gaps"])  # type: ignore[arg-type]
        stats["open_incidents"] += int(row["open_incidents"])
        stats["legal_holds"] += int(bool(row["legal_hold_active"]))

    owner_rows = [{"owner_team": owner, **values} for owner, values in sorted(owner_stats.items())]
    write_csv(
        output / "owner_gaps.csv",
        ["owner_team", "datasets", "blocked", "needs_work", "accepted_risk", "ready", "missing_controls", "downstream_gaps", "open_incidents", "legal_holds"],
        owner_rows,
    )

    incident_severities = {
        dataset: sorted(row["severity"] for row in rows)
        for dataset, rows in incident_rows.items()
    }
    plan_rows: list[dict[str, object]] = []
    for row in dataset_rows:
        if row["status"] == "ready":
            continue
        missing = list(row["missing_controls"])
        actions = [CONTROL_ACTIONS[control] for control in action_order if control in set(missing)]
        if row["legal_hold_active"]:
            actions.append(CONTROL_ACTIONS["legal_hold"])
        if row["status"] == "blocked":
            priority = "P0"
        elif row["status"] == "needs_work" and {"retention_limit", "downstream_delete", "open_incident"} & set(missing):
            priority = "P1"
        elif row["status"] == "needs_work":
            priority = "P2"
        else:
            priority = "P3"
        evidence = list(row["source_evidence_files"])
        evidence.extend(f"purge:{job_id}" for job_id in row["purge_jobs"])
        evidence.extend(f"export:{job_id}" for job_id in row["export_jobs"])
        evidence.extend(f"hold:{hold_id}" for hold_id in hold_ids_by_dataset.get(str(row["dataset_id"]), []))
        evidence.extend(f"incident:{severity}" for severity in incident_severities.get(str(row["dataset_id"]), []))
        plan_rows.append(
            {
                "dataset_id": row["dataset_id"],
                "owner_team": row["owner_team"],
                "priority": priority,
                "due_date": (report_date + timedelta(days=due_days[str(row["status"])])).isoformat(),
                "actions": ";".join(actions),
                "evidence": ";".join(evidence),
            }
        )
    plan_rows.sort(key=lambda row: (PRIORITY_RANK[str(row["priority"])], str(row["dataset_id"])))
    write_csv(
        output / "purge_plan.csv",
        ["dataset_id", "owner_team", "priority", "due_date", "actions", "evidence"],
        plan_rows,
    )

    summary = {
        "datasets": len(dataset_rows),
        "owners": len(owner_rows),
        "blocked": sum(1 for row in dataset_rows if row["status"] == "blocked"),
        "needs_work": sum(1 for row in dataset_rows if row["status"] == "needs_work"),
        "accepted_risk": sum(1 for row in dataset_rows if row["status"] == "accepted_risk"),
        "ready": sum(1 for row in dataset_rows if row["status"] == "ready"),
        "missing_controls": sum(len(row["missing_controls"]) for row in dataset_rows),  # type: ignore[arg-type]
        "downstream_delete_gaps": sum(len(row["downstream_delete_gaps"]) for row in dataset_rows),  # type: ignore[arg-type]
        "downstream_export_gaps": sum(len(row["downstream_export_gaps"]) for row in dataset_rows),  # type: ignore[arg-type]
        "open_incidents": sum(int(row["open_incidents"]) for row in dataset_rows),
        "legal_holds": sum(1 for row in dataset_rows if row["legal_hold_active"]),
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/app")
    parser.add_argument("--output", default="/app/output")
    args = parser.parse_args()
    build(Path(args.root), Path(args.output))


if __name__ == "__main__":
    main()
PY

python scripts/build_retention_audit.py

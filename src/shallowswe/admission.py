from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import tomllib

from .task_metadata import discover_tasks, is_official_calibration_status


ADMISSION_AUDIT_SCHEMA_VERSION = "shallowswe.admission_audit.v0.2"
ALTERNATE_SOLUTION_DIRS = ("solution_alt", "alternate_solution", "solution-alternate")


def audit_task_admission(root: Path) -> dict[str, Any]:
    """Audit task-local evidence required before snapshot admission."""

    task_rows: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    calibration_issue_counts: Counter[str] = Counter()

    for task in discover_tasks(root):
        is_official = is_official_calibration_status(task.calibration_status)
        row = _audit_one_task(task.path)
        row.update(
            {
                "task_id": task.task_id,
                "category": task.category,
                "size": task.size,
                "calibration_status": task.calibration_status,
                "official_candidate": is_official,
            }
        )
        row["admission_issues"] = _admission_issues(row) if is_official else []
        row["ready_for_snapshot"] = not row["admission_issues"]
        row["calibration_issues"] = _calibration_issues(row["calibration"]) if is_official else []
        row["ready_for_calibrated_snapshot"] = (
            is_official and row["ready_for_snapshot"] and not row["calibration_issues"]
        )
        for issue in row["admission_issues"]:
            issue_counts[issue] += 1
        for issue in row["calibration_issues"]:
            calibration_issue_counts[issue] += 1
        task_rows.append(row)

    official_rows = [row for row in task_rows if row["official_candidate"]]
    ready_rows = [row for row in official_rows if row["ready_for_snapshot"]]
    calibrated_ready_rows = [
        row for row in official_rows if row["ready_for_calibrated_snapshot"]
    ]

    return {
        "schema_version": ADMISSION_AUDIT_SCHEMA_VERSION,
        "tasks_root": str(root),
        "official_task_count": len(official_rows),
        "ready_task_count": len(ready_rows),
        "ready_for_snapshot": len(ready_rows) == len(official_rows),
        "ready_for_calibrated_snapshot_count": len(calibrated_ready_rows),
        "ready_for_calibrated_snapshot": (
            len(calibrated_ready_rows) == len(official_rows)
        ),
        "issue_counts": dict(sorted(issue_counts.items())),
        "calibration_issue_counts": dict(sorted(calibration_issue_counts.items())),
        "tasks": sorted(task_rows, key=lambda row: str(row["task_id"])),
    }


def _audit_one_task(path: Path) -> dict[str, Any]:
    verifier_path = path / "tests" / "test.sh"
    verifier_text = verifier_path.read_text() if verifier_path.exists() else ""
    alternate_paths = [
        path / name / "solve.sh"
        for name in ALTERNATE_SOLUTION_DIRS
    ]

    return {
        "has_instruction": (path / "instruction.md").exists(),
        "has_environment": (path / "environment").is_dir(),
        "has_verifier": verifier_path.exists(),
        "verifier_propagates_status": (
            "status=$?" in verifier_text and 'exit "$status"' in verifier_text
        ),
        "has_reference_solution": (path / "solution" / "solve.sh").exists(),
        "has_alternate_solution": any(candidate.exists() for candidate in alternate_paths),
        "accepted_alternate_solution_paths": [
            str(candidate.relative_to(path))
            for candidate in alternate_paths
            if candidate.exists()
        ],
        "calibration": _calibration_summary(path),
    }


def _admission_issues(row: dict[str, Any]) -> list[str]:
    checks = {
        "missing_instruction": row["has_instruction"],
        "missing_environment": row["has_environment"],
        "missing_verifier": row["has_verifier"],
        "verifier_does_not_propagate_status": row["verifier_propagates_status"],
        "missing_reference_solution": row["has_reference_solution"],
        "missing_alternate_solution": row["has_alternate_solution"],
    }
    return [issue for issue, passed in checks.items() if not passed]


def _calibration_summary(path: Path) -> dict[str, Any]:
    config_path = path / "task.toml"
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    calibration = raw.get("calibration")
    if not isinstance(calibration, dict):
        return {"has_calibration_provenance": False}

    ceiling = calibration.get("ceiling")
    floor = calibration.get("floor")
    return {
        "has_calibration_provenance": True,
        "calibration_snapshot_id": calibration.get("calibration_snapshot_id"),
        "admission_decision": calibration.get("admission_decision"),
        "size_assignment_decision": calibration.get("size_assignment_decision"),
        "ceiling": ceiling if isinstance(ceiling, dict) else {},
        "floor": floor if isinstance(floor, dict) else {},
    }


def _calibration_issues(calibration: dict[str, Any]) -> list[str]:
    if not calibration.get("has_calibration_provenance"):
        return ["missing_calibration_provenance"]

    issues: list[str] = []
    if calibration.get("admission_decision") != "accepted":
        issues.append("admission_decision_not_accepted")
    if calibration.get("size_assignment_decision") != "accepted":
        issues.append("size_assignment_not_accepted")
    ceiling = calibration.get("ceiling")
    if not isinstance(ceiling, dict) or not ceiling:
        issues.append("missing_ceiling_calibration")
    elif int(ceiling.get("one_shot_current_n") or 0) < int(ceiling.get("one_shot_target_n") or 0):
        issues.append("pending_ceiling_rollouts")
    floor = calibration.get("floor")
    if not isinstance(floor, dict) or not floor:
        issues.append("missing_floor_calibration")
    elif int(floor.get("one_shot_current_n") or 0) < int(floor.get("one_shot_target_n") or 0):
        issues.append("pending_floor_rollouts")
    return issues

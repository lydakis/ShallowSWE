from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json
import tomllib

from .budget import load_panel
from .task_metadata import discover_tasks


CALIBRATION_PLAN_SCHEMA_VERSION = "shallowswe.calibration_plan.v0.1"
CALIBRATION_PLAN_AUDIT_SCHEMA_VERSION = "shallowswe.calibration_plan_audit.v0.1"


def audit_calibration_plan(
    plan_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Validate the pre-registered calibration plan against the current checkout."""

    root = repo_root or Path.cwd()
    plan = json.loads(plan_path.read_text())
    issues: list[str] = []

    if plan.get("schema_version") != CALIBRATION_PLAN_SCHEMA_VERSION:
        issues.append("unsupported_schema_version")

    task_root = _repo_path(root, str(plan.get("task_root") or "tasks"))
    official_tasks = [
        task
        for task in discover_tasks(task_root)
        if task.calibration_status != "smoke"
    ]
    planned_task_count = int(plan.get("official_task_count") or 0)
    if planned_task_count != len(official_tasks):
        issues.append("official_task_count_mismatch")

    protocol = plan.get("protocol")
    if not isinstance(protocol, dict):
        issues.append("missing_protocol")
        protocol = {}
    issues.extend(_protocol_issues(protocol))

    run_group_reports = [
        _audit_run_group(
            root=root,
            group=group,
            official_tasks=official_tasks,
        )
        for group in plan.get("run_groups", [])
        if isinstance(group, dict)
    ]
    if not run_group_reports:
        issues.append("missing_run_groups")

    run_group_issue_counts: Counter[str] = Counter()
    for report in run_group_reports:
        for issue in report["issues"]:
            run_group_issue_counts[issue] += 1

    budget_status_counts = Counter(
        str(report["budget_status"])
        for report in run_group_reports
    )
    valid = not issues and not run_group_issue_counts
    ready_without_override = valid and not budget_status_counts.get("approval_required")

    return {
        "schema_version": CALIBRATION_PLAN_AUDIT_SCHEMA_VERSION,
        "plan": plan.get("name"),
        "snapshot_id": plan.get("snapshot_id"),
        "plan_path": str(plan_path),
        "task_root": str(task_root),
        "official_task_count": len(official_tasks),
        "planned_official_task_count": planned_task_count,
        "valid": valid,
        "ready_to_run_without_budget_override": ready_without_override,
        "issues": issues,
        "run_group_issue_counts": dict(sorted(run_group_issue_counts.items())),
        "budget_status_counts": dict(sorted(budget_status_counts.items())),
        "run_groups": run_group_reports,
    }


def _audit_run_group(
    *,
    root: Path,
    group: dict[str, Any],
    official_tasks: list[Any],
) -> dict[str, Any]:
    issues: list[str] = []
    row_ids = [str(row_id) for row_id in group.get("row_ids", [])]
    target_rollouts = int(group.get("target_rollouts_per_task") or 0)

    if not row_ids:
        issues.append("missing_row_ids")
    if target_rollouts < 1:
        issues.append("invalid_target_rollouts")
    if group.get("single_model_per_row") is not True:
        issues.append("single_model_per_row_not_declared")
    if group.get("mode") == "one_shot" and group.get("published_leaderboard") is not False:
        issues.append("one_shot_group_not_quarantined")

    panel_report = _audit_panel(root, str(group.get("panel") or ""), row_ids)
    issues.extend(panel_report["issues"])

    calibration_report = _audit_task_calibration_section(
        official_tasks=official_tasks,
        section=str(group.get("task_manifest_calibration_section") or ""),
        target_rollouts=target_rollouts,
    )
    issues.extend(calibration_report["issues"])

    budget_report = _audit_budget_gate(
        root=root,
        gate=group.get("budget_gate"),
        official_task_count=len(official_tasks),
        target_rollouts=target_rollouts,
    )
    issues.extend(budget_report["issues"])

    planned_attempts = len(official_tasks) * len(row_ids) * target_rollouts
    return {
        "id": group.get("id"),
        "mode": group.get("mode"),
        "purpose": group.get("purpose"),
        "panel": group.get("panel"),
        "row_ids": row_ids,
        "target_rollouts_per_task": target_rollouts,
        "planned_attempts": planned_attempts,
        "current_rollouts_per_task_min": calibration_report["current_rollouts_per_task_min"],
        "current_rollouts_per_task_max": calibration_report["current_rollouts_per_task_max"],
        "tasks_below_target": calibration_report["tasks_below_target"],
        "panel_allows_fallbacks": panel_report["panel_allows_fallbacks"],
        "budget_status": budget_report["budget_status"],
        "estimated_full_panel_cost_usd": budget_report["estimated_full_panel_cost_usd"],
        "budget_limit_usd": budget_report["budget_limit_usd"],
        "requires_explicit_approval": budget_report["requires_explicit_approval"],
        "issues": issues,
    }


def _protocol_issues(protocol: dict[str, Any]) -> list[str]:
    checks = {
        "single_model_run_invariant_not_declared": protocol.get("single_model_run_invariant"),
        "fallbacks_not_forbidden": protocol.get("no_fallbacks"),
        "calibration_rollouts_not_quarantined": (
            protocol.get("calibration_rollouts_excluded_from_publish")
        ),
    }
    issues = [issue for issue, passed in checks.items() if passed is not True]
    if protocol.get("one_shot_ceiling_pass_threshold") != 0.75:
        issues.append("unexpected_ceiling_threshold")
    if protocol.get("repair_loop_solve_rate_floor") != 0.9:
        issues.append("unexpected_repair_loop_solve_rate_floor")
    if protocol.get("published_repair_loop_seeds_per_task_model_config") != 10:
        issues.append("unexpected_published_repair_loop_seed_count")
    return issues


def _audit_panel(root: Path, panel_ref: str, row_ids: list[str]) -> dict[str, Any]:
    issues: list[str] = []
    if not panel_ref:
        return {"issues": ["missing_panel"], "panel_allows_fallbacks": None}

    panel_path = _repo_path(root, panel_ref)
    try:
        panel = load_panel(panel_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return {"issues": ["invalid_panel"], "panel_allows_fallbacks": None}

    panel_rows = panel.get("rows", [])
    panel_row_ids = {
        str(row.get("id"))
        for row in panel_rows
        if isinstance(row, dict) and row.get("id")
    }
    missing_rows = sorted(set(row_ids) - panel_row_ids)
    if missing_rows:
        issues.append("unknown_panel_row_id")

    defaults = panel.get("defaults")
    provider_routing = defaults.get("provider_routing") if isinstance(defaults, dict) else None
    panel_allows_fallbacks = (
        provider_routing.get("allow_fallbacks")
        if isinstance(provider_routing, dict)
        else None
    )
    if panel_allows_fallbacks is not False:
        issues.append("panel_does_not_disable_fallbacks")

    return {
        "issues": issues,
        "panel_allows_fallbacks": panel_allows_fallbacks,
    }


def _audit_task_calibration_section(
    *,
    official_tasks: list[Any],
    section: str,
    target_rollouts: int,
) -> dict[str, Any]:
    if section not in {"ceiling", "floor"}:
        return {
            "issues": ["unknown_task_calibration_section"],
            "current_rollouts_per_task_min": 0,
            "current_rollouts_per_task_max": 0,
            "tasks_below_target": len(official_tasks),
        }

    issues: list[str] = []
    current_counts: list[int] = []
    tasks_below_target = 0
    for task in official_tasks:
        with (task.path / "task.toml").open("rb") as handle:
            raw = tomllib.load(handle)
        calibration = raw.get("calibration")
        section_config = calibration.get(section) if isinstance(calibration, dict) else None
        if not isinstance(section_config, dict):
            issues.append(f"missing_{section}_calibration")
            current_counts.append(0)
            tasks_below_target += 1
            continue

        section_target = int(section_config.get("one_shot_target_n") or 0)
        current = int(section_config.get("one_shot_current_n") or 0)
        current_counts.append(current)
        if section_target != target_rollouts:
            issues.append(f"{section}_target_mismatch")
        if current < target_rollouts:
            tasks_below_target += 1

    return {
        "issues": sorted(set(issues)),
        "current_rollouts_per_task_min": min(current_counts) if current_counts else 0,
        "current_rollouts_per_task_max": max(current_counts) if current_counts else 0,
        "tasks_below_target": tasks_below_target,
    }


def _audit_budget_gate(
    *,
    root: Path,
    gate: Any,
    official_task_count: int,
    target_rollouts: int,
) -> dict[str, Any]:
    if not isinstance(gate, dict):
        return _budget_report("missing", ["missing_budget_gate"])

    estimate_ref = gate.get("estimate_artifact")
    estimate_path = gate.get("estimate_path")
    issues: list[str] = []
    if not isinstance(estimate_ref, str) or not estimate_ref:
        return _budget_report("missing", ["missing_budget_estimate"])
    if not isinstance(estimate_path, list) or not estimate_path:
        return _budget_report("missing", ["missing_budget_estimate_path"])

    try:
        estimate_root = json.loads(_repo_path(root, estimate_ref).read_text())
        estimate = _resolve_path(estimate_root, [str(part) for part in estimate_path])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return _budget_report("missing", ["invalid_budget_estimate"])

    if not isinstance(estimate, dict):
        return _budget_report("missing", ["invalid_budget_estimate"])

    if int(estimate.get("task_count") or 0) != official_task_count:
        issues.append("budget_task_count_mismatch")
    if int(estimate.get("rollouts_per_task") or 0) != target_rollouts:
        issues.append("budget_rollout_count_mismatch")
    if int(estimate.get("missing_price_rows") or 0) != 0:
        issues.append("budget_missing_prices")

    max_budget = gate.get("max_budget_usd")
    if max_budget is not None and estimate.get("budget_limit_usd") != max_budget:
        issues.append("budget_limit_mismatch")

    over_budget = estimate.get("over_budget") is True
    requires_approval = (
        over_budget and gate.get("requires_explicit_approval_if_over_budget") is True
    )
    if over_budget and not requires_approval:
        issues.append("over_budget_without_explicit_approval_gate")
    budget_status = "approval_required" if requires_approval else "within_budget"
    if estimate.get("estimated_full_panel_cost_usd") is None:
        budget_status = "missing"

    return {
        "issues": issues,
        "budget_status": budget_status,
        "estimated_full_panel_cost_usd": estimate.get("estimated_full_panel_cost_usd"),
        "budget_limit_usd": estimate.get("budget_limit_usd"),
        "requires_explicit_approval": requires_approval,
    }


def _budget_report(status: str, issues: list[str]) -> dict[str, Any]:
    return {
        "issues": issues,
        "budget_status": status,
        "estimated_full_panel_cost_usd": None,
        "budget_limit_usd": None,
        "requires_explicit_approval": False,
    }


def _resolve_path(raw: Any, path: list[str]) -> Any:
    current = raw
    for part in path:
        if not isinstance(current, dict):
            raise TypeError(part)
        current = current[part]
    return current


def _repo_path(root: Path, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return root / candidate

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from .budget import load_panel
from .task_metadata import discover_tasks


REPAIR_LOOP_PREVIEW_PLAN_SCHEMA_VERSION = "shallowswe.repair_loop_preview_plan.v0.1"
REPAIR_LOOP_PREVIEW_PLAN_AUDIT_SCHEMA_VERSION = "shallowswe.repair_loop_preview_plan_audit.v0.1"
REQUIRED_FEEDBACK_CLASSES = {
    "generic_failure",
    "runtime_error",
    "missing_required_artifact",
    "output_mismatch",
}


def audit_repair_loop_preview_plan(
    plan_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    plan = json.loads(plan_path.read_text())
    issues: list[str] = []
    blockers: list[str] = []

    if plan.get("schema_version") != REPAIR_LOOP_PREVIEW_PLAN_SCHEMA_VERSION:
        issues.append("unsupported_schema_version")
    if plan.get("mode") != "bounded_repair_loop_preview":
        issues.append("unsupported_mode")

    task_root = _repo_path(root, str(plan.get("task_root") or "tasks"))
    tasks_by_id = {task.task_id: task for task in discover_tasks(task_root)}
    task_ids = [str(task_id) for task_id in plan.get("task_ids", [])]
    selected_tasks = []
    for task_id in task_ids:
        task = tasks_by_id.get(task_id)
        if task is None:
            issues.append("unknown_task_id")
            continue
        selected_tasks.append(task)
        if task.calibration_status == "smoke":
            issues.append("preview_subset_includes_smoke_task")

    cell_counts = Counter(f"{task.category}/{task.size}" for task in selected_tasks)
    if len(cell_counts) != 9:
        issues.append("preview_subset_missing_category_size_cell")
    if set(cell_counts.values()) != {2}:
        issues.append("preview_subset_not_two_tasks_per_cell")

    panel_path = _repo_path(root, str(plan.get("model_panel") or ""))
    try:
        panel = load_panel(panel_path)
    except (OSError, ValueError, json.JSONDecodeError):
        issues.append("invalid_model_panel")
        panel = {"rows": []}
    model_rows = panel.get("rows") if isinstance(panel.get("rows"), list) else []

    seeds = int(plan.get("repair_loop_seeds_per_task_model_config") or 0)
    if seeds < 1:
        issues.append("invalid_repair_loop_seed_count")

    protocol_report = _audit_protocol(plan.get("protocol"))
    issues.extend(protocol_report["issues"])

    budget_report = _audit_budget_gate(
        plan.get("budget_gate"),
        root=root,
        expected_rows=len(selected_tasks) * len(model_rows) * seeds,
    )
    issues.extend(budget_report["issues"])
    blockers.extend(budget_report["blockers"])

    valid = not issues
    return {
        "schema_version": REPAIR_LOOP_PREVIEW_PLAN_AUDIT_SCHEMA_VERSION,
        "plan": plan.get("name"),
        "snapshot_id": plan.get("snapshot_id"),
        "plan_path": str(plan_path),
        "valid": valid,
        "ready_to_launch": valid and not blockers,
        "issues": sorted(set(issues)),
        "blockers": sorted(set(blockers)),
        "task_count": len(selected_tasks),
        "model_rows": len(model_rows),
        "repair_loop_seeds_per_task_model_config": seeds,
        "estimated_total_rows": len(selected_tasks) * len(model_rows) * seeds,
        "cell_counts": dict(sorted(cell_counts.items())),
        "verifier_submission_cap": protocol_report["verifier_submission_cap"],
        "agent_step_cap": protocol_report["agent_step_cap"],
        "per_row_dollar_cap_usd": protocol_report["dollar_cap_usd"],
        "global_hard_stop_usd": budget_report["global_hard_stop_usd"],
        "budget_limit_usd": budget_report["budget_limit_usd"],
        "budget_estimate_path": budget_report["budget_estimate_path"],
        "budget_estimates": budget_report["budget_estimates"],
        "theoretical_spend_if_every_row_hits_dollar_cap_usd": (
            protocol_report["dollar_cap_usd"] * len(selected_tasks) * len(model_rows) * seeds
            if protocol_report["dollar_cap_usd"] is not None
            else None
        ),
    }


def _audit_protocol(raw_protocol: Any) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(raw_protocol, dict):
        return {
            "issues": ["missing_protocol"],
            "verifier_submission_cap": None,
            "agent_step_cap": None,
            "dollar_cap_usd": None,
        }

    if raw_protocol.get("single_model_run_invariant") is not True:
        issues.append("single_model_run_invariant_not_declared")
    if raw_protocol.get("no_fallbacks") is not True:
        issues.append("fallbacks_not_forbidden")
    if raw_protocol.get("requires_conversation_continuation") is not True:
        issues.append("conversation_continuation_not_required")
    if raw_protocol.get("requires_filesystem_continuation") is not True:
        issues.append("filesystem_continuation_not_required")
    if REQUIRED_FEEDBACK_CLASSES - set(raw_protocol.get("allowed_feedback_classes", [])):
        issues.append("missing_allowed_feedback_class")

    verifier_submission_cap = int(raw_protocol.get("verifier_submission_cap") or 0)
    agent_step_cap = int(raw_protocol.get("agent_step_cap") or 0)
    dollar_cap_usd = _positive_float_or_none(raw_protocol.get("dollar_cap_usd"))
    if verifier_submission_cap < 1:
        issues.append("invalid_verifier_submission_cap")
    if agent_step_cap < 1:
        issues.append("invalid_agent_step_cap")
    if dollar_cap_usd is None:
        issues.append("invalid_dollar_cap")

    return {
        "issues": issues,
        "verifier_submission_cap": verifier_submission_cap,
        "agent_step_cap": agent_step_cap,
        "dollar_cap_usd": dollar_cap_usd,
    }


def _audit_budget_gate(
    raw_gate: Any,
    *,
    root: Path,
    expected_rows: int,
) -> dict[str, Any]:
    if not isinstance(raw_gate, dict):
        return _budget_report(
            issues=["missing_budget_gate"],
            blockers=["missing_budget_gate"],
        )

    issues: list[str] = []
    blockers: list[str] = []
    budget_limit = _positive_float_or_none(raw_gate.get("max_budget_usd"))
    hard_stop = _positive_float_or_none(raw_gate.get("global_hard_stop_usd"))
    if budget_limit is None:
        issues.append("invalid_budget_limit")
    if hard_stop is None:
        issues.append("invalid_global_hard_stop")
        blockers.append("missing_global_hard_stop")
    if budget_limit is not None and hard_stop is not None and budget_limit > hard_stop:
        issues.append("budget_limit_exceeds_global_hard_stop")
        blockers.append("budget_limit_exceeds_global_hard_stop")
    if raw_gate.get("requires_explicit_approval_if_over_budget") is not True:
        issues.append("budget_override_not_guarded")

    estimate_artifact = raw_gate.get("estimate_artifact")
    if not isinstance(estimate_artifact, str) or not estimate_artifact:
        return _budget_report(
            issues=[*issues, "missing_budget_estimate"],
            blockers=[*blockers, "missing_budget_estimate"],
            budget_limit_usd=budget_limit,
            global_hard_stop_usd=hard_stop,
        )

    estimate_path = _repo_path(root, estimate_artifact)
    try:
        estimate = json.loads(estimate_path.read_text())
    except (OSError, json.JSONDecodeError):
        return _budget_report(
            issues=[*issues, "invalid_budget_estimate"],
            blockers=[*blockers, "invalid_budget_estimate"],
            budget_limit_usd=budget_limit,
            global_hard_stop_usd=hard_stop,
            budget_estimate_path=str(estimate_path),
        )

    if int(estimate.get("estimated_total_rows") or 0) != expected_rows:
        issues.append("budget_estimate_row_count_mismatch")

    budget_estimates: dict[str, float] = {}
    estimates = estimate.get("estimates")
    if isinstance(estimates, dict):
        for estimate_name, raw_estimate in estimates.items():
            if not isinstance(raw_estimate, dict):
                continue
            full_cost = raw_estimate.get("estimated_full_panel_cost_usd")
            if isinstance(full_cost, int | float):
                budget_estimates[str(estimate_name)] = float(full_cost)
                if hard_stop is not None and full_cost > hard_stop:
                    blockers.append(f"{estimate_name}_exceeds_global_hard_stop")
    if not budget_estimates:
        issues.append("missing_full_panel_cost_estimate")
        blockers.append("missing_full_panel_cost_estimate")

    return _budget_report(
        issues=issues,
        blockers=blockers,
        budget_limit_usd=budget_limit,
        global_hard_stop_usd=hard_stop,
        budget_estimate_path=str(estimate_path),
        budget_estimates=budget_estimates,
    )


def _budget_report(
    *,
    issues: list[str],
    blockers: list[str],
    budget_limit_usd: float | None = None,
    global_hard_stop_usd: float | None = None,
    budget_estimate_path: str | None = None,
    budget_estimates: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "issues": issues,
        "blockers": blockers,
        "budget_limit_usd": budget_limit_usd,
        "global_hard_stop_usd": global_hard_stop_usd,
        "budget_estimate_path": budget_estimate_path,
        "budget_estimates": budget_estimates or {},
    }


def _positive_float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0.0 else None


def _repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path

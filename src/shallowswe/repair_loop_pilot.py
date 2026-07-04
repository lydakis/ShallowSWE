from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from .task_metadata import CATEGORY_ORDER, SIZE_ORDER, discover_tasks


REPAIR_LOOP_PILOT_PLAN_SCHEMA_VERSION = "shallowswe.repair_loop_pilot_plan.v0.1"
REPAIR_LOOP_PILOT_PLAN_AUDIT_SCHEMA_VERSION = "shallowswe.repair_loop_pilot_plan_audit.v0.1"

FINAL_PROTOCOL_CONTINUATION = "conversation_and_filesystem"
REQUIRED_FEEDBACK_CLASSES = {
    "generic_failure",
    "runtime_error",
    "missing_required_artifact",
    "output_mismatch",
}
REQUIRED_FORK_CAPABILITIES = {
    "resume prior trajectory/messages",
    "condition every repair submission on the same conversation state",
    "append sanitized verifier feedback as user message",
    "continue in same workspace without resetting files",
    "emit cumulative usage across repair submissions",
    "preserve transcript hash across submissions",
}


def audit_repair_loop_pilot_plan(
    plan_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Audit whether a repair-loop pilot plan can produce final-protocol evidence."""

    root = repo_root or Path.cwd()
    plan = json.loads(plan_path.read_text())
    issues: list[str] = []
    blockers: list[str] = []

    if plan.get("schema_version") != REPAIR_LOOP_PILOT_PLAN_SCHEMA_VERSION:
        issues.append("unsupported_schema_version")

    task_root = _repo_path(root, str(plan.get("task_root") or "tasks"))
    tasks_by_id = {
        task.task_id: task
        for task in discover_tasks(task_root)
    }
    task_ids = [str(task_id) for task_id in plan.get("task_ids", [])]
    if not task_ids:
        issues.append("missing_task_ids")

    selected_tasks = []
    missing_task_ids = []
    smoke_task_ids = []
    for task_id in task_ids:
        task = tasks_by_id.get(task_id)
        if task is None:
            missing_task_ids.append(task_id)
            continue
        selected_tasks.append(task)
        if task.calibration_status == "smoke":
            smoke_task_ids.append(task_id)

    if missing_task_ids:
        issues.append("unknown_task_id")
    if smoke_task_ids:
        issues.append("pilot_subset_includes_smoke_task")

    categories = Counter(task.category for task in selected_tasks)
    sizes = Counter(task.size for task in selected_tasks)
    if set(categories) != set(CATEGORY_ORDER):
        issues.append("pilot_subset_missing_category_coverage")
    if set(sizes) != set(SIZE_ORDER):
        issues.append("pilot_subset_missing_size_coverage")

    protocol_report = _audit_protocol(plan.get("protocol"))
    issues.extend(protocol_report["issues"])

    model_report = _audit_model_configs(plan.get("model_configs"))
    issues.extend(model_report["issues"])
    blockers.extend(model_report["blockers"])

    budget_report = _audit_budget_gate(plan.get("budget_gate"))
    issues.extend(budget_report["issues"])

    fork_report = _audit_fork_requirement(plan.get("fork_requirement"))
    issues.extend(fork_report["issues"])
    if fork_report["required"] and not fork_report["satisfied"]:
        blockers.append("mini_swe_fork_or_equivalent_agent_continuation_required")

    valid = not issues
    ready_for_final_protocol_pilot = valid and not blockers
    can_run_protocol_smoke = valid and bool(selected_tasks) and bool(model_report["model_configs"])

    return {
        "schema_version": REPAIR_LOOP_PILOT_PLAN_AUDIT_SCHEMA_VERSION,
        "plan": plan.get("name"),
        "snapshot_id": plan.get("snapshot_id"),
        "plan_path": str(plan_path),
        "task_root": str(task_root),
        "valid": valid,
        "ready_for_final_protocol_pilot": ready_for_final_protocol_pilot,
        "can_run_protocol_smoke": can_run_protocol_smoke,
        "issues": sorted(set(issues)),
        "blockers": sorted(set(blockers)),
        "task_count": len(selected_tasks),
        "task_ids": task_ids,
        "categories": dict(sorted(categories.items())),
        "sizes": dict(sorted(sizes.items())),
        "allowed_feedback_classes": protocol_report["allowed_feedback_classes"],
        "model_config_count": len(model_report["model_configs"]),
        "final_protocol_eligible_model_configs": model_report[
            "final_protocol_eligible_model_configs"
        ],
        "non_eligible_model_configs": model_report["non_eligible_model_configs"],
        "fork_required": fork_report["required"],
        "fork_satisfied": fork_report["satisfied"],
        "fork_missing_capabilities": fork_report["missing_capabilities"],
        "budget_limit_usd": budget_report["budget_limit_usd"],
    }


def _audit_protocol(raw_protocol: Any) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(raw_protocol, dict):
        return {
            "issues": ["missing_protocol"],
            "allowed_feedback_classes": [],
        }

    if raw_protocol.get("requires_conversation_continuation") is not True:
        issues.append("conversation_continuation_not_required")
    if raw_protocol.get("requires_filesystem_continuation") is not True:
        issues.append("filesystem_continuation_not_required")
    if raw_protocol.get("single_model_run_invariant") is not True:
        issues.append("single_model_run_invariant_not_declared")
    if raw_protocol.get("no_fallbacks") is not True:
        issues.append("fallbacks_not_forbidden")

    allowed_feedback_classes = [
        str(value)
        for value in raw_protocol.get("allowed_feedback_classes", [])
    ]
    if not REQUIRED_FEEDBACK_CLASSES <= set(allowed_feedback_classes):
        issues.append("missing_allowed_feedback_class")

    if int(raw_protocol.get("verifier_submission_cap") or 0) < 2:
        issues.append("invalid_verifier_submission_cap")
    if int(raw_protocol.get("agent_step_cap") or 0) < 1:
        issues.append("invalid_agent_step_cap")
    if int(raw_protocol.get("wall_time_cap_seconds") or 0) < 1:
        issues.append("invalid_wall_time_cap")
    if float(raw_protocol.get("dollar_cap_usd") or 0.0) <= 0.0:
        issues.append("invalid_dollar_cap")

    return {
        "issues": issues,
        "allowed_feedback_classes": allowed_feedback_classes,
    }


def _audit_model_configs(raw_configs: Any) -> dict[str, Any]:
    issues: list[str] = []
    blockers: list[str] = []
    if not isinstance(raw_configs, list) or not raw_configs:
        return {
            "issues": ["missing_model_configs"],
            "blockers": [],
            "model_configs": [],
            "final_protocol_eligible_model_configs": [],
            "non_eligible_model_configs": [],
        }

    configs = [
        config
        for config in raw_configs
        if isinstance(config, dict)
    ]
    if len(configs) != len(raw_configs):
        issues.append("invalid_model_config")

    final_eligible: list[str] = []
    non_eligible: list[str] = []
    for config in configs:
        config_id = str(config.get("id") or "")
        if not config_id:
            issues.append("missing_model_config_id")
            continue
        if config.get("single_model_per_run") is not True:
            issues.append("model_config_single_model_not_declared")
        if config.get("allow_fallbacks") is not False:
            issues.append("model_config_allows_fallbacks")

        continuation = str(config.get("continuation_capability") or "")
        is_final_eligible = config.get("final_protocol_eligible") is True
        if is_final_eligible and continuation == FINAL_PROTOCOL_CONTINUATION:
            final_eligible.append(config_id)
        else:
            non_eligible.append(config_id)
        if is_final_eligible and continuation != FINAL_PROTOCOL_CONTINUATION:
            issues.append("eligible_model_without_conversation_continuation")

    if not final_eligible:
        blockers.append("no_model_config_with_conversation_continuation")

    return {
        "issues": issues,
        "blockers": blockers,
        "model_configs": configs,
        "final_protocol_eligible_model_configs": final_eligible,
        "non_eligible_model_configs": non_eligible,
    }


def _audit_budget_gate(raw_gate: Any) -> dict[str, Any]:
    if not isinstance(raw_gate, dict):
        return {
            "issues": ["missing_budget_gate"],
            "budget_limit_usd": None,
        }

    issues: list[str] = []
    budget_limit = float(raw_gate.get("max_budget_usd") or 0.0)
    if budget_limit <= 0.0:
        issues.append("invalid_budget_limit")
    if raw_gate.get("requires_explicit_approval_if_over_budget") is not True:
        issues.append("budget_override_not_guarded")
    return {
        "issues": issues,
        "budget_limit_usd": budget_limit,
    }


def _audit_fork_requirement(raw_requirement: Any) -> dict[str, Any]:
    if not isinstance(raw_requirement, dict):
        return {
            "issues": ["missing_fork_requirement"],
            "required": False,
            "satisfied": False,
            "missing_capabilities": sorted(REQUIRED_FORK_CAPABILITIES),
        }

    required = raw_requirement.get("required") is True
    satisfied = raw_requirement.get("satisfied") is True
    must_support = {
        str(value)
        for value in raw_requirement.get("must_support", [])
    }
    missing_capabilities = sorted(REQUIRED_FORK_CAPABILITIES - must_support)
    issues: list[str] = []
    if required and missing_capabilities:
        issues.append("fork_requirement_missing_capability")
    source_dir = raw_requirement.get("source_dir")
    if satisfied and (
        not isinstance(source_dir, str)
        or not (Path(source_dir).expanduser() / "pyproject.toml").exists()
    ):
        issues.append("fork_satisfied_source_dir_invalid")

    return {
        "issues": issues,
        "required": required,
        "satisfied": satisfied,
        "missing_capabilities": missing_capabilities,
    }


def _repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path

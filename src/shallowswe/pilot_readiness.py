from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from .identity import agent_policy_id, model_config_id
from .pilot_launch import audit_pilot_launch_plan
from .pilot_schedule import audit_pilot_schedule
from .task_metadata import discover_tasks
from .task_quality import build_task_quality_report


PILOT_MANIFEST_SCHEMA_VERSION = "shallowswe.pilot_manifest.v0.3"
PILOT_READINESS_SCHEMA_VERSION = "shallowswe.pilot_readiness.v0.1"
EXPECTED_STAGE_TOTALS = {
    "codex_development": 66,
    "kaggle_canary": 16,
    "permissive_collection": 72,
    "fresh_anchor_confirmation": 24,
}


def audit_pilot_readiness(
    manifest_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    manifest = json.loads(manifest_path.read_text())
    issues: list[str] = []
    blockers: list[str] = []

    if manifest.get("schema_version") != PILOT_MANIFEST_SCHEMA_VERSION:
        issues.append("unsupported_schema_version")
    if manifest.get("methodology_version") != "v0.4.2":
        issues.append("methodology_version_mismatch")
    if manifest.get("release_class") != "protocol_validation":
        issues.append("invalid_release_class")

    task_root = _repo_path(root, manifest.get("task_root") or "tasks")
    task_report = _audit_tasks(
        task_root,
        manifest.get("task_ids"),
        manifest.get("canary_task_ids"),
        manifest.get("confirmation_task_ids"),
    )
    issues.extend(task_report["issues"])
    blockers.extend(task_report["blockers"])

    runner_report = _audit_runner_contract(manifest.get("runner_contract"))
    issues.extend(runner_report["issues"])

    identity_report = _audit_identities(manifest.get("model_configs"), manifest.get("agent_policy"))
    issues.extend(identity_report["issues"])
    blockers.extend(identity_report["blockers"])

    policy_report = _audit_permissive_policy(manifest.get("temporary_permissive_policy"))
    issues.extend(policy_report["issues"])

    stage4_report = _audit_stage4_selection_policy(manifest.get("stage4_selection_policy"))
    issues.extend(stage4_report["issues"])

    measurement_report = _audit_measurement_policy(manifest.get("pilot_measurement_policy"))
    issues.extend(measurement_report["issues"])

    trajectory_report = _audit_trajectory_plan(
        manifest.get("trajectory_plan"),
        task_report["task_count"],
        task_report["confirmation_task_ids"],
    )
    issues.extend(trajectory_report["issues"])

    funding_report = _audit_funding_gate(manifest.get("funding_gate"))
    issues.extend(funding_report["issues"])

    budget_report = _audit_budget_preflight(manifest.get("budget_preflight"), funding_report)
    issues.extend(budget_report["issues"])

    freeze_report = _audit_freeze_artifacts(manifest.get("freeze_artifacts"))
    blockers.extend(freeze_report["blockers"])
    schedule_report = _audit_schedule(root, manifest_path, manifest.get("freeze_artifacts"))
    issues.extend(schedule_report["issues"])
    blockers.extend(schedule_report["blockers"])
    launch_report = _audit_launch_plan(root, manifest_path, manifest.get("freeze_artifacts"))
    issues.extend(launch_report["issues"])
    blockers.extend(launch_report["blockers"])

    structurally_valid = not issues
    ready_for_official_canary = structurally_valid and not blockers
    return {
        "schema_version": PILOT_READINESS_SCHEMA_VERSION,
        "manifest": manifest.get("name"),
        "manifest_path": str(manifest_path),
        "methodology_version": manifest.get("methodology_version"),
        "structurally_valid": structurally_valid,
        "ready_for_official_canary": ready_for_official_canary,
        "issues": sorted(set(issues)),
        "blockers": sorted(set(blockers)),
        "task_count": task_report["task_count"],
        "categories": task_report["categories"],
        "confirmation_task_ids": task_report["confirmation_task_ids"],
        "quality_ready_tasks": task_report["quality_ready_tasks"],
        "routine_review_ready_tasks": task_report["routine_review_ready_tasks"],
        "model_config_ids": identity_report["model_config_ids"],
        "agent_policy_ids": identity_report["agent_policy_ids"],
        "stage_totals": trajectory_report["stage_totals"],
        "official_core_trajectories": trajectory_report["official_core_trajectories"],
        "funding_gate": funding_report,
        "budget_preflight": budget_report,
        "pilot_schedule": schedule_report,
        "pilot_launch_plan": launch_report,
    }


def _audit_tasks(
    task_root: Path,
    raw_task_ids: Any,
    raw_canary_ids: Any,
    raw_confirmation_ids: Any,
) -> dict[str, Any]:
    issues: list[str] = []
    blockers: list[str] = []
    task_ids = [str(value) for value in raw_task_ids] if isinstance(raw_task_ids, list) else []
    canary_ids = [str(value) for value in raw_canary_ids] if isinstance(raw_canary_ids, list) else []
    confirmation_ids = (
        [str(value) for value in raw_confirmation_ids]
        if isinstance(raw_confirmation_ids, list)
        else []
    )
    discovered = {task.task_id: task for task in discover_tasks(task_root)}
    missing = sorted(set(task_ids) - discovered.keys())
    if len(task_ids) != 6:
        issues.append("pilot_requires_six_tasks")
    if missing:
        issues.append("unknown_task_id")
    if len(canary_ids) != 2 or not set(canary_ids) <= set(task_ids):
        issues.append("invalid_canary_task_ids")
    selected = [discovered[task_id] for task_id in task_ids if task_id in discovered]
    categories = Counter(task.category for task in selected)
    if categories != Counter({"artifact": 2, "code": 2, "workflow": 2}):
        issues.append("pilot_requires_two_tasks_per_category")
    confirmation_categories = Counter(
        discovered[task_id].category
        for task_id in confirmation_ids
        if task_id in discovered
    )
    if (
        len(confirmation_ids) != 3
        or len(set(confirmation_ids)) != 3
        or not set(confirmation_ids) <= set(task_ids)
        or confirmation_categories != Counter({"artifact": 1, "code": 1, "workflow": 1})
    ):
        issues.append("invalid_confirmation_task_ids")

    quality_rows = {
        str(row["task_id"]): row
        for row in build_task_quality_report(task_root)["tasks"]
        if row["task_id"] in task_ids
    }
    quality_ready = sorted(
        task_id
        for task_id, row in quality_rows.items()
        if row["executed_quality_evidence_complete"]
    )
    routine_ready = sorted(
        task_id for task_id, row in quality_rows.items() if row["routine_review_complete"]
    )
    if len(quality_ready) != len(task_ids):
        blockers.append("pilot_task_quality_incomplete")
    if len(routine_ready) != len(task_ids):
        blockers.append("pilot_routine_review_incomplete")
    return {
        "issues": issues,
        "blockers": blockers,
        "task_count": len(selected),
        "categories": dict(sorted(categories.items())),
        "confirmation_task_ids": confirmation_ids,
        "quality_ready_tasks": quality_ready,
        "routine_review_ready_tasks": routine_ready,
    }


def _audit_runner_contract(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"issues": ["missing_runner_contract"]}
    issues = []
    if raw.get("canonical_official_runner") != "kaggle":
        issues.append("official_runner_must_be_kaggle")
    if raw.get("development_runner") != "codex_subscription":
        issues.append("development_runner_must_be_codex_subscription")
    if raw.get("development_evidence_class") != "development_dry_run":
        issues.append("development_evidence_class_must_be_isolated")
    if raw.get("development_release_class") != "development_dry_run":
        issues.append("development_release_class_must_be_isolated")
    if raw.get("pool_unequal_agent_policies") is not False:
        issues.append("unequal_agent_policy_pooling_not_forbidden")
    return {"issues": issues}


def _audit_identities(raw_configs: Any, raw_policy: Any) -> dict[str, Any]:
    issues: list[str] = []
    blockers: list[str] = []
    configs = raw_configs if isinstance(raw_configs, list) else []
    if {row.get("role") for row in configs if isinstance(row, dict)} != {
        "primary_anchor",
        "floor_low",
        "floor_strong",
    }:
        issues.append("invalid_model_roles")
    policy = raw_policy if isinstance(raw_policy, dict) else {}
    policy_canonical = policy.get("canonical") if isinstance(policy.get("canonical"), dict) else {}
    recorded_agent_ids = (
        policy.get("agent_policy_ids_by_model_role")
        if isinstance(policy.get("agent_policy_ids_by_model_role"), dict)
        else {}
    )
    model_ids = []
    agent_ids = []
    for row in configs:
        if not isinstance(row, dict) or not isinstance(row.get("canonical"), dict):
            issues.append("invalid_model_config")
            continue
        canonical = row["canonical"]
        identifier = model_config_id(canonical)
        model_ids.append(identifier)
        if any(value is None for value in canonical.values()):
            blockers.append("model_config_canonical_json_incomplete")
        if row.get("model_config_id") not in (None, identifier):
            issues.append("model_config_id_mismatch")
        if row.get("status") == "frozen" and row.get("model_config_id") is None:
            blockers.append("model_config_id_not_recorded")
        if row.get("status") != "frozen":
            blockers.append("model_config_not_frozen")
        agent_identifier = agent_policy_id(policy_canonical, model_config_id=identifier)
        agent_ids.append(agent_identifier)
        if recorded_agent_ids.get(row.get("role")) != agent_identifier:
            blockers.append("agent_policy_id_not_recorded_or_mismatched")
    if policy.get("status") != "frozen":
        blockers.append("agent_policy_not_frozen")
    if any(value is None for value in policy_canonical.values()):
        blockers.append("agent_policy_canonical_json_incomplete")
    return {
        "issues": issues,
        "blockers": blockers,
        "model_config_ids": model_ids,
        "agent_policy_ids": agent_ids,
    }


def _audit_permissive_policy(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"issues": ["missing_temporary_permissive_policy"]}
    issues = []
    submission_limit = int(raw.get("verifier_submission_limit") or 0)
    step_limit = int(raw.get("agent_step_limit") or 0)
    submission_candidates = [int(value) for value in raw.get("candidate_verifier_submission_caps", [])]
    step_candidates = [int(value) for value in raw.get("candidate_agent_step_caps", [])]
    if submission_limit != 16 or not submission_candidates or max(submission_candidates) >= submission_limit:
        issues.append("submission_candidates_not_strictly_inside_limit")
    if step_limit != 256 or not step_candidates or max(step_candidates) >= step_limit:
        issues.append("step_candidates_not_strictly_inside_limit")
    if raw.get("cap_disclosure") != "undisclosed":
        issues.append("caps_must_be_undisclosed")
    return {"issues": issues}


def _audit_stage4_selection_policy(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"issues": ["missing_stage4_selection_policy"]}
    issues = []
    if float(raw.get("success_capture_target") or 0.0) != 0.99:
        issues.append("invalid_stage4_success_capture_target")
    if raw.get("reported_budget_coverage_targets") != [0.75, 0.9, 1.0]:
        issues.append("invalid_stage4_reported_coverage_targets")
    if float(raw.get("selected_development_coverage_target") or 0.0) != 0.75:
        issues.append("invalid_stage4_development_coverage_target")
    if int(raw.get("max_budget_band_bumps") or 0) != 1:
        issues.append("invalid_stage4_budget_band_bumps")
    if raw.get("pressure_taxonomies") != [2, 3]:
        issues.append("invalid_stage4_pressure_taxonomies")
    if int(raw.get("confirmation_minimum_successes") or 0) != 7:
        issues.append("invalid_stage4_confirmation_minimum")
    if int(raw.get("confirmation_attempts") or 0) != 8:
        issues.append("invalid_stage4_confirmation_attempts")
    return {"issues": issues}


def _audit_measurement_policy(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"issues": ["missing_pilot_measurement_policy"]}
    issues = []
    expected = {
        "first_submit_source": "permissive_repair_loop_prefix",
        "standalone_one_shot_stage": False,
        "pressure_use": "descriptive_protocol_signal",
        "full_budget_and_confirmation_scope": (
            "v1_freeze_machinery_demonstrated_on_preregistered_subset"
        ),
    }
    for key, value in expected.items():
        if raw.get(key) != value:
            issues.append(f"invalid_pilot_measurement_policy:{key}")
    return {"issues": issues}


def _audit_trajectory_plan(
    raw: Any,
    task_count: int,
    confirmation_task_ids: list[str],
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"issues": ["missing_trajectory_plan"], "stage_totals": {}, "official_core_trajectories": 0}
    issues = []
    if set(raw) != set(EXPECTED_STAGE_TOTALS):
        issues.append("unexpected_trajectory_stage")
    totals = {name: int((raw.get(name) or {}).get("total") or 0) for name in EXPECTED_STAGE_TOTALS}
    if totals != EXPECTED_STAGE_TOTALS:
        issues.append("trajectory_stage_total_mismatch")
    permissive = raw.get("permissive_collection") or {}
    expected_permissive = task_count * (
        int(permissive.get("anchor_per_task") or 0)
        + 2 * int(permissive.get("each_floor_per_task") or 0)
    )
    if expected_permissive != totals["permissive_collection"]:
        issues.append("permissive_allocation_total_mismatch")
    if int(permissive.get("anchor_proposal_per_task") or 0) != 4:
        issues.append("anchor_proposal_split_mismatch")
    if int(permissive.get("anchor_development_check_per_task") or 0) != 2:
        issues.append("anchor_development_split_mismatch")
    confirmation = raw.get("fresh_anchor_confirmation") or {}
    if [str(value) for value in confirmation.get("task_ids", [])] != confirmation_task_ids:
        issues.append("confirmation_task_ids_mismatch")
    expected_confirmation = len(confirmation_task_ids) * int(
        confirmation.get("anchor_per_task") or 0
    )
    if expected_confirmation != totals["fresh_anchor_confirmation"]:
        issues.append("confirmation_allocation_total_mismatch")
    if int(confirmation.get("minimum_successes_per_task") or 0) != 7:
        issues.append("confirmation_success_threshold_mismatch")
    official_core = sum(total for name, total in totals.items() if name != "codex_development")
    if official_core != 112:
        issues.append("official_core_trajectory_total_mismatch")
    return {"issues": issues, "stage_totals": totals, "official_core_trajectories": official_core}


def _audit_funding_gate(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"issues": ["missing_funding_gate"]}
    issues = []
    expected = {
        "core_kaggle_limit_usd": 200.0,
        "targeted_extension_reserve_usd": 100.0,
        "daily_launch_soft_limit_usd": 160.0,
        "daily_hard_limit_usd": 200.0,
        "openrouter_cash_cap_usd": 25.0,
    }
    for key, value in expected.items():
        if float(raw.get(key) or 0.0) != value:
            issues.append(f"invalid_{key}")
    if raw.get("requires_explicit_approval") is not True:
        issues.append("funding_override_not_guarded")
    return {"issues": issues, **{key: raw.get(key) for key in expected}}


def _audit_budget_preflight(raw: Any, funding: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"issues": ["missing_budget_preflight"]}
    issues = []
    stage_estimates = raw.get("stage_high_estimates_usd")
    expected_stages = {
        "kaggle_canary",
        "permissive_collection",
        "fresh_anchor_confirmation",
    }
    if not isinstance(stage_estimates, dict) or set(stage_estimates) != expected_stages:
        issues.append("invalid_stage_high_estimates")
        calculated_core = 0.0
    else:
        calculated_core = sum(float(value) for value in stage_estimates.values())
    declared_core = float(raw.get("core_high_estimate_usd") or 0.0)
    if calculated_core != declared_core:
        issues.append("core_high_estimate_mismatch")
    if declared_core > float(funding.get("core_kaggle_limit_usd") or 0.0):
        issues.append("core_high_estimate_exceeds_funding_limit")
    if float(raw.get("canary_launch_reserve_usd") or 0.0) < float(
        (stage_estimates or {}).get("kaggle_canary") or 0.0
    ):
        issues.append("canary_reserve_below_high_estimate")
    if raw.get("price_basis") != "planning_estimate_pending_frozen_price_sheet":
        issues.append("invalid_budget_price_basis")
    return {
        "issues": issues,
        "stage_high_estimates_usd": stage_estimates,
        "core_high_estimate_usd": declared_core,
        "headroom_usd": float(funding.get("core_kaggle_limit_usd") or 0.0) - declared_core,
        "price_basis": raw.get("price_basis"),
    }


def _audit_schedule(root: Path, manifest_path: Path, raw_freeze: Any) -> dict[str, Any]:
    if not isinstance(raw_freeze, dict) or not raw_freeze.get("pilot_schedule"):
        return {"issues": ["missing_pilot_schedule_path"], "blockers": []}
    schedule_path = _repo_path(root, str(raw_freeze["pilot_schedule"]))
    if not schedule_path.is_file():
        return {"issues": ["pilot_schedule_file_missing"], "blockers": []}
    report = audit_pilot_schedule(manifest_path, schedule_path)
    blockers = []
    frozen_hash = raw_freeze.get("pilot_schedule_hash")
    if frozen_hash not in (None, "") and frozen_hash != report["schedule_sha256"]:
        blockers.append("pilot_schedule_hash_mismatch")
    return {
        **report,
        "issues": [f"pilot_{issue}" for issue in report["issues"]],
        "blockers": blockers,
    }


def _audit_launch_plan(root: Path, manifest_path: Path, raw_freeze: Any) -> dict[str, Any]:
    if not isinstance(raw_freeze, dict):
        return {"issues": ["missing_pilot_launch_plan_path"], "blockers": []}
    schedule_value = raw_freeze.get("pilot_schedule")
    launch_value = raw_freeze.get("pilot_launch_plan")
    if not schedule_value or not launch_value:
        return {"issues": ["missing_pilot_launch_plan_path"], "blockers": []}
    schedule_path = _repo_path(root, str(schedule_value))
    launch_path = _repo_path(root, str(launch_value))
    if not launch_path.is_file():
        return {"issues": ["pilot_launch_plan_file_missing"], "blockers": []}
    report = audit_pilot_launch_plan(manifest_path, schedule_path, launch_path)
    blockers = []
    frozen_hash = raw_freeze.get("pilot_launch_plan_hash")
    if frozen_hash not in (None, "") and frozen_hash != report["launch_plan_sha256"]:
        blockers.append("pilot_launch_plan_hash_mismatch")
    return {
        **report,
        "issues": [f"pilot_{issue}" for issue in report["issues"]],
        "blockers": blockers,
    }


def _audit_freeze_artifacts(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"blockers": ["missing_freeze_artifacts"]}
    missing = sorted(key for key, value in raw.items() if value in (None, "", []))
    return {"blockers": [f"freeze_artifact_missing:{key}" for key in missing]}


def _repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path

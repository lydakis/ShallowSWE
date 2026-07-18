from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from .identity import canonical_json


PILOT_LAUNCH_PLAN_SCHEMA_VERSION = "shallowswe.pilot_launch_plan.v0.1"
STAGE_ORDER = {
    "codex_development": 1,
    "kaggle_canary": 2,
    "permissive_collection": 3,
    "fresh_anchor_confirmation": 5,
    "preliminary_scoring": 6,
}


def build_pilot_launch_plan(
    manifest_path: Path,
    schedule_path: Path,
    *,
    plan_class: str = "official_pilot",
) -> dict[str, Any]:
    if plan_class not in {"official_pilot", "development_shadow"}:
        raise ValueError(f"unsupported launch plan class: {plan_class}")
    manifest = json.loads(manifest_path.read_text())
    schedule = json.loads(schedule_path.read_text())
    official_configs = {row["role"]: row for row in manifest["model_configs"]}
    development_configs = {
        row["role"]: row for row in manifest.get("development_model_configs", [])
    }
    shadow_configs = {
        row["role"]: row
        for row in manifest.get("development_shadow_model_configs", [])
    }
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in schedule["rows"]:
        key = (row["stage"], row["model_role"], row["mode"])
        grouped.setdefault(key, []).append(row)

    units = []
    for (stage, role, mode), rows in sorted(
        grouped.items(),
        key=lambda item: (STAGE_ORDER[item[0][0]], item[0][1], item[0][2]),
    ):
        task_ids = sorted({row["task_id"] for row in rows})
        seeds_by_task = {
            task_id: sorted(row["rollout_seed"] for row in rows if row["task_id"] == task_id)
            for task_id in task_ids
        }
        development = stage == "codex_development"
        config = (
            development_configs.get(role)
            if development
            else shadow_configs.get(role)
            if plan_class == "development_shadow"
            else official_configs.get(role)
        )
        if config is None:
            raise ValueError(f"manifest does not define {stage}/{role} model identity")
        official = stage != "codex_development"
        confirmation = stage == "fresh_anchor_confirmation"
        frozen_policy_stage = confirmation or stage == "preliminary_scoring"
        unit_identity = {
            "manifest": manifest["name"],
            "plan_class": plan_class,
            "stage": stage,
            "model_role": role,
            "mode": mode,
        }
        units.append(
            {
                **unit_identity,
                "launch_unit_id": _launch_unit_id(unit_identity),
                "runner": "kaggle" if official else "codex_subscription",
                "kaggle_task_name": (
                    _kaggle_task_name(
                        plan_class=plan_class,
                        stage=stage,
                        role=role,
                        mode=mode,
                    )
                    if official
                    else None
                ),
                "model": config["canonical"]["requested_model"],
                "reasoning_effort": config["canonical"]["reasoning_effort"],
                "model_config_id": rows[0]["model_config_id"],
                "agent_policy_id": rows[0]["agent_policy_id"],
                "task_ids": task_ids,
                "rollout_seeds_by_task": seeds_by_task,
                "trajectory_ids": sorted(row["trajectory_id"] for row in rows),
                "expected_trajectories": len(rows),
                "policy": {
                    "verifier_submission_cap": (
                        None
                        if frozen_policy_stage
                        else 1 if mode == "one_shot" else 16
                    ),
                    "agent_step_cap": 256,
                    "safety_dollar_cap_usd": None if frozen_policy_stage else 5.0,
                    "cap_disclosure": "undisclosed",
                },
                "evidence_class": rows[0]["evidence_class"],
                "release_class": rows[0]["release_class"],
                "funding_pool": rows[0]["funding_pool"],
                "launch_status": _launch_status(
                    plan_class=plan_class,
                    stage=stage,
                    official_runner=official,
                    confirmation=confirmation,
                ),
            }
        )

    official_count = (
        sum(unit["expected_trajectories"] for unit in units if unit["runner"] == "kaggle")
        if plan_class == "official_pilot"
        else 0
    )
    payload = {
        "schema_version": PILOT_LAUNCH_PLAN_SCHEMA_VERSION,
        "plan_class": plan_class,
        "manifest": manifest["name"],
        "schedule_sha256": schedule["schedule_sha256"],
        "units": units,
        "launch_unit_count": len(units),
        "trajectory_count": sum(unit["expected_trajectories"] for unit in units),
        "official_trajectory_count": official_count,
        "development_trajectory_count": (
            sum(unit["expected_trajectories"] for unit in units)
            if plan_class == "development_shadow"
            else sum(
                unit["expected_trajectories"]
                for unit in units
                if unit["runner"] == "codex_subscription"
            )
        ),
        "official_launch_gate": (
            "pilot-readiness ready_for_official_canary=true"
            if plan_class == "official_pilot"
            else "not_applicable_development_shadow"
        ),
    }
    payload["launch_plan_sha256"] = (
        f"sha256:{hashlib.sha256(canonical_json(payload).encode()).hexdigest()}"
    )
    return payload


def write_pilot_launch_plan(
    manifest_path: Path,
    schedule_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    payload = build_pilot_launch_plan(manifest_path, schedule_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def audit_pilot_launch_plan(
    manifest_path: Path,
    schedule_path: Path,
    launch_plan_path: Path,
) -> dict[str, Any]:
    expected = build_pilot_launch_plan(manifest_path, schedule_path)
    actual = json.loads(launch_plan_path.read_text())
    issues = [
        f"launch_plan_{key}_mismatch"
        for key in expected
        if actual.get(key) != expected.get(key)
    ]
    return {
        "schema_version": "shallowswe.pilot_launch_plan_audit.v0.1",
        "valid": not issues,
        "issues": sorted(issues),
        "launch_plan_path": str(launch_plan_path),
        "launch_unit_count": expected["launch_unit_count"],
        "trajectory_count": expected["trajectory_count"],
        "official_trajectory_count": expected["official_trajectory_count"],
        "launch_plan_sha256": expected["launch_plan_sha256"],
    }


def _launch_unit_id(identity: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(identity).encode()).hexdigest()
    return f"plu_sha256_{digest}"


def _launch_status(
    *,
    plan_class: str,
    stage: str,
    official_runner: bool,
    confirmation: bool,
) -> str:
    if plan_class == "development_shadow":
        if stage == "kaggle_canary":
            return "development_ready"
        if stage == "permissive_collection":
            return "blocked_by_development_canary"
        if confirmation:
            return "blocked_by_stage4_policy_freeze"
        if stage == "preliminary_scoring":
            return "blocked_by_fresh_anchor_confirmation"
        raise ValueError(f"development shadow does not support stage: {stage}")
    if confirmation:
        return "blocked_by_stage4_policy_freeze"
    if official_runner:
        return "blocked_by_pilot_readiness"
    return "development_ready"


def _kaggle_task_name(*, plan_class: str, stage: str, role: str, mode: str) -> str:
    prefix = (
        "shallowswe-development-shadow-v0-1"
        if plan_class == "development_shadow"
        else "shallowswe-pilot-v0-3"
    )
    return f"{prefix}-{stage}-{role}-{mode}".replace("_", "-")

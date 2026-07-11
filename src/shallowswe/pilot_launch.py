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
}


def build_pilot_launch_plan(manifest_path: Path, schedule_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    schedule = json.loads(schedule_path.read_text())
    configs = {row["role"]: row for row in manifest["model_configs"]}
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
        config = configs[role]
        official = stage != "codex_development"
        confirmation = stage == "fresh_anchor_confirmation"
        unit_identity = {
            "manifest": manifest["name"],
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
                    f"shallowswe-pilot-v0-3-{stage}-{role}-{mode}".replace("_", "-")
                    if official
                    else None
                ),
                "model": config["canonical"]["requested_model"],
                "reasoning_effort": config["canonical"]["reasoning_effort"],
                "model_config_id": config["model_config_id"],
                "agent_policy_id": manifest["agent_policy"]["agent_policy_ids_by_model_role"][role],
                "task_ids": task_ids,
                "rollout_seeds_by_task": seeds_by_task,
                "trajectory_ids": sorted(row["trajectory_id"] for row in rows),
                "expected_trajectories": len(rows),
                "policy": {
                    "verifier_submission_cap": (
                        None
                        if confirmation
                        else 1 if mode == "one_shot" else 16
                    ),
                    "agent_step_cap": 256,
                    "safety_dollar_cap_usd": None if confirmation else 5.0,
                    "cap_disclosure": "undisclosed",
                },
                "evidence_class": rows[0]["evidence_class"],
                "funding_pool": rows[0]["funding_pool"],
                "launch_status": (
                    "blocked_by_stage4_policy_freeze"
                    if confirmation
                    else "blocked_by_pilot_readiness" if official else "development_ready"
                ),
            }
        )

    official_count = sum(unit["expected_trajectories"] for unit in units if unit["runner"] == "kaggle")
    payload = {
        "schema_version": PILOT_LAUNCH_PLAN_SCHEMA_VERSION,
        "manifest": manifest["name"],
        "schedule_sha256": schedule["schedule_sha256"],
        "units": units,
        "launch_unit_count": len(units),
        "trajectory_count": sum(unit["expected_trajectories"] for unit in units),
        "official_trajectory_count": official_count,
        "official_launch_gate": "pilot-readiness ready_for_official_canary=true",
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

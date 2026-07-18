from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from .identity import agent_policy_id, canonical_json, model_config_id
from .pilot_launch import build_pilot_launch_plan
from .pilot_schedule import build_pilot_schedule


DEVELOPMENT_SHADOW_SCHEDULE_SCHEMA_VERSION = "shallowswe.development_shadow_schedule.v0.1"


def build_development_shadow_plan(
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the isolated 190-row Kaggle pipeline shakedown."""

    base = build_pilot_schedule(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    shadow_name = f"{manifest['name']}-development-shadow-v0.1"
    task_ids = [str(value) for value in manifest["task_ids"]]
    canary_ids = [str(value) for value in manifest["canary_task_ids"]]
    configs = {
        str(row["role"]): row["canonical"]
        for row in manifest.get("development_shadow_model_configs", [])
    }
    policy = manifest["agent_policy"]["canonical"]
    if not configs:
        raise ValueError("manifest lacks development-shadow model identities")
    rows: list[dict[str, Any]] = []

    def add(
        stage: str,
        tasks: list[str],
        role: str,
        mode: str,
        replicates: int,
        *,
        seed_offset: int,
        cohort: str | None = None,
        replicate_offset: int = 0,
    ) -> None:
        if role not in configs:
            raise ValueError(f"manifest lacks development-shadow role: {role}")
        model_id = model_config_id(configs[role])
        policy_id = agent_policy_id(policy, model_config_id=model_id)
        for task_id in tasks:
            for replicate in range(1 + replicate_offset, replicates + replicate_offset + 1):
                identity = {
                    "manifest": shadow_name,
                    "stage": stage,
                    "task_id": task_id,
                    "model_role": role,
                    "mode": mode,
                    "replicate": replicate,
                    "cohort": cohort,
                }
                rows.append(
                    {
                        **identity,
                        "trajectory_id": _trajectory_id(identity),
                        "rollout_seed": seed_offset + replicate - 1,
                        "model_config_id": model_id,
                        "agent_policy_id": policy_id,
                        "evidence_class": "development_dry_run",
                        "release_class": "development_dry_run",
                        "funding_pool": "kaggle_grant_development",
                    }
                )

    add("kaggle_canary", canary_ids, "primary_anchor", "one_shot", 2, seed_offset=5000)
    for role in ("primary_anchor", "floor_low", "floor_strong"):
        add(
            "kaggle_canary",
            canary_ids,
            role,
            "permissive_repair_loop",
            2,
            seed_offset=5000,
        )
    add(
        "permissive_collection",
        task_ids,
        "primary_anchor",
        "permissive_repair_loop",
        4,
        seed_offset=6000,
        cohort="budget_proposal",
    )
    add(
        "permissive_collection",
        task_ids,
        "primary_anchor",
        "permissive_repair_loop",
        2,
        seed_offset=6000,
        cohort="development_check",
        replicate_offset=4,
    )
    for role in ("floor_low", "floor_strong"):
        add(
            "permissive_collection",
            task_ids,
            role,
            "permissive_repair_loop",
            3,
            seed_offset=6000,
        )
    add(
        "fresh_anchor_confirmation",
        task_ids,
        "primary_anchor",
        "frozen_repair_loop",
        8,
        seed_offset=7000,
        cohort="fresh_confirmation",
    )
    for role in ("candidate_luna", "candidate_sol", "candidate_gemini"):
        add(
            "preliminary_scoring",
            task_ids,
            role,
            "frozen_repair_loop",
            3,
            seed_offset=8000,
            cohort="fresh_candidate_panel",
        )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["stage"]] = counts.get(row["stage"], 0) + 1
    schedule = {
        "schema_version": DEVELOPMENT_SHADOW_SCHEDULE_SCHEMA_VERSION,
        "plan_class": "development_shadow",
        "manifest": shadow_name,
        "source_manifest": manifest["name"],
        "methodology_version": manifest["methodology_version"],
        "identity_status": base["identity_status"],
        "task_ids": task_ids,
        "rows": rows,
        "stage_counts": dict(sorted(counts.items())),
        "trajectory_count": len(rows),
        "schedule_sha256": f"sha256:{hashlib.sha256(canonical_json(rows).encode()).hexdigest()}",
    }
    with _temporary_schedule(schedule) as schedule_path:
        launch_plan = build_pilot_launch_plan(
            manifest_path,
            schedule_path,
            plan_class="development_shadow",
        )
    launch_plan["manifest"] = shadow_name
    launch_plan["source_manifest"] = manifest["name"]
    launch_plan["schedule_sha256"] = schedule["schedule_sha256"]
    launch_plan["launch_plan_sha256"] = _payload_hash(launch_plan, "launch_plan_sha256")
    return schedule, launch_plan


def write_development_shadow_plan(
    manifest_path: Path,
    schedule_path: Path,
    launch_plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    schedule, launch_plan = build_development_shadow_plan(manifest_path)
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    launch_plan_path.parent.mkdir(parents=True, exist_ok=True)
    schedule_path.write_text(json.dumps(schedule, indent=2) + "\n")
    launch_plan_path.write_text(json.dumps(launch_plan, indent=2) + "\n")
    return schedule, launch_plan


def audit_development_shadow_plan(
    manifest_path: Path,
    schedule_path: Path,
    launch_plan_path: Path,
) -> dict[str, Any]:
    expected_schedule, expected_launch = build_development_shadow_plan(manifest_path)
    actual_schedule = json.loads(schedule_path.read_text())
    actual_launch = json.loads(launch_plan_path.read_text())
    issues = []
    if actual_schedule != expected_schedule:
        issues.append("development_shadow_schedule_mismatch")
    if actual_launch != expected_launch:
        issues.append("development_shadow_launch_plan_mismatch")
    return {
        "schema_version": "shallowswe.development_shadow_audit.v0.1",
        "valid": not issues,
        "issues": issues,
        "trajectory_count": expected_schedule["trajectory_count"],
        "stage_counts": expected_schedule["stage_counts"],
        "development_ready_units": sum(
            1
            for unit in expected_launch["units"]
            if unit["launch_status"] == "development_ready"
        ),
        "official_evidence_rows": sum(
            1
            for row in expected_schedule["rows"]
            if row["evidence_class"] == "official_pilot"
            or row["release_class"] == "protocol_validation"
        ),
    }


def _trajectory_id(identity: dict[str, Any]) -> str:
    return f"pt_sha256_{hashlib.sha256(canonical_json(identity).encode()).hexdigest()}"


def _payload_hash(payload: dict[str, Any], hash_field: str) -> str:
    unsigned = {key: value for key, value in payload.items() if key != hash_field}
    return f"sha256:{hashlib.sha256(canonical_json(unsigned).encode()).hexdigest()}"


class _temporary_schedule:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> Path:
        from tempfile import TemporaryDirectory

        self._temporary_directory = TemporaryDirectory()
        path = Path(self._temporary_directory.name) / "schedule.json"
        path.write_text(json.dumps(self.payload))
        return path

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._temporary_directory.cleanup()

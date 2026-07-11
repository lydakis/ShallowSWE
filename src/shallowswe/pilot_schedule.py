from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from .identity import agent_policy_id, canonical_json, model_config_id


PILOT_SCHEDULE_SCHEMA_VERSION = "shallowswe.pilot_schedule.v0.1"


def build_pilot_schedule(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    task_ids = [str(value) for value in manifest["task_ids"]]
    canary_ids = [str(value) for value in manifest["canary_task_ids"]]
    confirmation_ids = [str(value) for value in manifest["confirmation_task_ids"]]
    role_configs = {str(row["role"]): row["canonical"] for row in manifest["model_configs"]}
    policy = manifest["agent_policy"]["canonical"]
    rows: list[dict[str, Any]] = []

    def add(
        stage: str,
        tasks: list[str],
        role: str,
        mode: str,
        replicates: int,
        *,
        evidence_class: str,
        funding_pool: str,
        cohort: str | None = None,
        replicate_offset: int = 0,
    ) -> None:
        model_id = model_config_id(role_configs[role])
        policy_id = agent_policy_id(policy, model_config_id=model_id)
        for task_id in tasks:
            for replicate in range(1 + replicate_offset, replicates + replicate_offset + 1):
                identity = {
                    "manifest": manifest["name"],
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
                        "rollout_seed": replicate - 1,
                        "model_config_id": model_id,
                        "agent_policy_id": policy_id,
                        "evidence_class": evidence_class,
                        "funding_pool": funding_pool,
                    }
                )

    for role, one_shot_replicates in (
        ("primary_anchor", 2),
        ("floor_low", 3),
        ("floor_strong", 3),
    ):
        add(
            "codex_development",
            task_ids,
            role,
            "one_shot",
            one_shot_replicates,
            evidence_class="development",
            funding_pool="codex_subscription",
        )
        add(
            "codex_development",
            task_ids,
            role,
            "repair_loop_smoke",
            1,
            evidence_class="development",
            funding_pool="codex_subscription",
        )

    add(
        "kaggle_canary",
        canary_ids,
        "primary_anchor",
        "one_shot",
        2,
        evidence_class="official_pilot",
        funding_pool="kaggle_grant",
    )
    for role in ("primary_anchor", "floor_low", "floor_strong"):
        add(
            "kaggle_canary",
            canary_ids,
            role,
            "permissive_repair_loop",
            2,
            evidence_class="official_pilot",
            funding_pool="kaggle_grant",
        )

    add(
        "permissive_collection",
        task_ids,
        "primary_anchor",
        "permissive_repair_loop",
        4,
        evidence_class="official_pilot",
        funding_pool="kaggle_grant",
        cohort="budget_proposal",
    )
    add(
        "permissive_collection",
        task_ids,
        "primary_anchor",
        "permissive_repair_loop",
        2,
        evidence_class="official_pilot",
        funding_pool="kaggle_grant",
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
            evidence_class="official_pilot",
            funding_pool="kaggle_grant",
        )

    add(
        "fresh_anchor_confirmation",
        confirmation_ids,
        "primary_anchor",
        "frozen_repair_loop",
        8,
        evidence_class="official_pilot",
        funding_pool="kaggle_grant",
        cohort="fresh_confirmation",
    )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["stage"]] = counts.get(row["stage"], 0) + 1
    return {
        "schema_version": PILOT_SCHEDULE_SCHEMA_VERSION,
        "manifest": manifest["name"],
        "methodology_version": manifest["methodology_version"],
        "identity_status": "provisional" if _has_pending_identity(manifest) else "frozen",
        "rows": rows,
        "stage_counts": dict(sorted(counts.items())),
        "trajectory_count": len(rows),
        "schedule_sha256": f"sha256:{hashlib.sha256(canonical_json(rows).encode()).hexdigest()}",
    }


def audit_pilot_schedule(manifest_path: Path, schedule_path: Path) -> dict[str, Any]:
    expected = build_pilot_schedule(manifest_path)
    actual = json.loads(schedule_path.read_text())
    issues = []
    for key in (
        "schema_version",
        "manifest",
        "methodology_version",
        "identity_status",
        "stage_counts",
        "trajectory_count",
        "schedule_sha256",
        "rows",
    ):
        if actual.get(key) != expected.get(key):
            issues.append(f"schedule_{key}_mismatch")
    trajectory_ids = [row.get("trajectory_id") for row in actual.get("rows", [])]
    if len(trajectory_ids) != len(set(trajectory_ids)):
        issues.append("duplicate_trajectory_id")
    return {
        "schema_version": "shallowswe.pilot_schedule_audit.v0.1",
        "manifest": expected["manifest"],
        "schedule_path": str(schedule_path),
        "valid": not issues,
        "issues": sorted(set(issues)),
        "identity_status": expected["identity_status"],
        "stage_counts": expected["stage_counts"],
        "trajectory_count": expected["trajectory_count"],
        "schedule_sha256": expected["schedule_sha256"],
    }


def write_pilot_schedule(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    schedule = build_pilot_schedule(manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schedule, indent=2) + "\n")
    return schedule


def _trajectory_id(identity: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(identity).encode()).hexdigest()
    return f"pt_sha256_{digest}"


def _has_pending_identity(manifest: dict[str, Any]) -> bool:
    if manifest.get("agent_policy", {}).get("status") != "frozen":
        return True
    return any(row.get("status") != "frozen" for row in manifest.get("model_configs", []))

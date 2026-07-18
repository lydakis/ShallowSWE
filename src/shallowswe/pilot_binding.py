from __future__ import annotations

from typing import Any


def resolve_model_config(
    configs: list[dict[str, Any]],
    *,
    requested_model: str,
    model_config_id: str | None,
) -> dict[str, Any]:
    """Resolve a frozen config without collapsing same-model effort variants."""
    matches = [
        row
        for row in configs
        if row.get("canonical", {}).get("requested_model") == requested_model
        and (model_config_id is None or row.get("model_config_id") == model_config_id)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one frozen model config for "
            f"{requested_model!r}/{model_config_id!r}, found {len(matches)}"
        )
    return matches[0]


def resolve_launch_unit(
    launch_plan: dict[str, Any],
    launch_unit_id: str,
) -> dict[str, Any]:
    matches = [
        unit for unit in launch_plan.get("units", []) if unit.get("launch_unit_id") == launch_unit_id
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one launch unit for {launch_unit_id!r}, found {len(matches)}"
        )
    unit = matches[0]
    if unit.get("runner") != "kaggle":
        raise RuntimeError(f"Launch unit is not assigned to Kaggle: {launch_unit_id}")
    plan_class = launch_plan.get("plan_class", "official_pilot")
    if plan_class == "official_pilot":
        allowed_status = "official_ready"
    elif plan_class == "development_shadow":
        if (
            unit.get("evidence_class") != "development_dry_run"
            or unit.get("release_class") != "development_dry_run"
        ):
            raise RuntimeError(
                f"Development shadow launch unit is not isolated: {launch_unit_id}"
            )
        allowed_status = "development_ready"
    else:
        raise RuntimeError(f"Unknown launch plan class: {plan_class!r}")
    if unit.get("launch_status") != allowed_status:
        raise RuntimeError(
            f"Launch unit is not launchable: {launch_unit_id} "
            f"({unit.get('launch_status') or 'missing_launch_status'})"
        )
    return unit


def launch_matrix(unit: dict[str, Any]) -> tuple[list[str], list[int]]:
    task_ids = [str(value) for value in unit.get("task_ids", [])]
    seeds_by_task = unit.get("rollout_seeds_by_task") or {}
    seed_sets = [[int(seed) for seed in seeds_by_task.get(task_id, [])] for task_id in task_ids]
    if not task_ids or not seed_sets or any(seeds != seed_sets[0] for seeds in seed_sets):
        raise RuntimeError("Kaggle launch unit must define one shared seed matrix for every task")
    seeds = seed_sets[0]
    if seeds != list(range(seeds[0], seeds[0] + len(seeds))):
        raise RuntimeError("Kaggle launch unit seeds must be one contiguous reserved range")
    if len(task_ids) * len(seeds) != int(unit.get("expected_trajectories") or 0):
        raise RuntimeError("Kaggle launch unit matrix does not match expected_trajectories")
    return task_ids, seeds


def resolve_trajectory(
    unit: dict[str, Any],
    schedule: dict[str, Any],
    *,
    task_id: str,
    rollout_seed: int,
    model_config_id: str,
    requested_model: str,
) -> dict[str, Any]:
    if unit.get("model_config_id") != model_config_id or unit.get("model") != requested_model:
        raise RuntimeError("Kaggle model does not match the frozen launch unit")
    allowed_ids = set(unit.get("trajectory_ids", []))
    matches = [
        row
        for row in schedule.get("rows", [])
        if row.get("trajectory_id") in allowed_ids
        and row.get("stage") == unit.get("stage")
        and row.get("model_role") == unit.get("model_role")
        and row.get("mode") == unit.get("mode")
        and row.get("task_id") == task_id
        and int(row.get("rollout_seed", -1)) == rollout_seed
        and row.get("model_config_id") == model_config_id
        and row.get("agent_policy_id") == unit.get("agent_policy_id")
        and row.get("evidence_class") == unit.get("evidence_class")
        and row.get("release_class") == unit.get("release_class")
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one pre-registered trajectory for "
            f"{task_id} seed {rollout_seed}, found {len(matches)}"
        )
    return matches[0]

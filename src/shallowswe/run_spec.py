from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from .identity import canonical_json


RUN_SPEC_SCHEMA_VERSION = "shallowswe.run_spec.v0.1"


def load_run_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text())
    validate_run_spec(spec)
    return spec


def audit_run_spec(path: Path) -> dict[str, Any]:
    spec = load_run_spec(path)
    return {
        "schema_version": "shallowswe.run_spec_audit.v0.1",
        "valid": True,
        "run_spec_id": spec["run_spec_id"],
        "experiment_id": spec["experiment_id"],
        "unit_count": len(spec["units"]),
        "trajectory_count": sum(
            len(unit["task_ids"]) * len(unit["rollout_seeds"])
            for unit in spec["units"]
        ),
        "run_spec_sha256": run_spec_sha256(spec),
    }


def validate_run_spec(spec: dict[str, Any]) -> None:
    """Validate execution facts without interpreting experiment metadata."""
    if spec.get("schema_version") != RUN_SPEC_SCHEMA_VERSION:
        raise ValueError(f"unsupported run-spec schema: {spec.get('schema_version')!r}")
    for field in ("run_spec_id", "experiment_id", "task_suite_version"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"run spec requires non-empty {field}")

    model_configs = _unique_rows(spec.get("model_configs"), "model_config_id")
    agent_policies = _unique_rows(spec.get("agent_policies"), "agent_policy_id")
    units = _unique_rows(spec.get("units"), "run_unit_id")
    if not units:
        raise ValueError("run spec requires at least one unit")

    for identifier, config in model_configs.items():
        canonical = config.get("canonical")
        if not isinstance(canonical, dict):
            raise ValueError(f"model config {identifier} requires canonical identity")
        for field in ("requested_model", "expected_resolved_model"):
            if not isinstance(canonical.get(field), str) or not canonical[field]:
                raise ValueError(f"model config {identifier} requires canonical.{field}")

    for identifier, policy in agent_policies.items():
        if not isinstance(policy.get("canonical"), dict):
            raise ValueError(f"agent policy {identifier} requires canonical identity")

    for identifier, unit in units.items():
        if not isinstance(unit.get("runner"), str) or not unit["runner"]:
            raise ValueError(f"run unit {identifier} requires a runner")
        if unit.get("model_config_id") not in model_configs:
            raise ValueError(f"run unit {identifier} references unknown model_config_id")
        if unit.get("agent_policy_id") not in agent_policies:
            raise ValueError(f"run unit {identifier} references unknown agent_policy_id")
        task_ids = unit.get("task_ids")
        if (
            not isinstance(task_ids, list)
            or not task_ids
            or any(not isinstance(value, str) or not value for value in task_ids)
            or len(task_ids) != len(set(task_ids))
        ):
            raise ValueError(f"run unit {identifier} requires unique task_ids")
        seeds = unit.get("rollout_seeds")
        if (
            not isinstance(seeds, list)
            or not seeds
            or any(not isinstance(value, int) or value < 0 for value in seeds)
            or len(seeds) != len(set(seeds))
        ):
            raise ValueError(f"run unit {identifier} requires unique non-negative rollout_seeds")
        limits = unit.get("limits")
        if not isinstance(limits, dict):
            raise ValueError(f"run unit {identifier} requires limits")
        _positive_int(limits, "verifier_submissions", identifier)
        _positive_int(limits, "agent_steps", identifier)
        _positive_int(limits, "wall_time_seconds", identifier)
        dollar_cap = limits.get("dollar_usd")
        if dollar_cap is not None and float(dollar_cap) <= 0:
            raise ValueError(f"run unit {identifier} requires positive limits.dollar_usd")
        metadata = unit.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"run unit {identifier} metadata must be an object")

    expected_hash = spec.get("run_spec_sha256")
    if expected_hash is not None and expected_hash != run_spec_sha256(spec):
        raise ValueError("run_spec_sha256 does not match run spec")


def run_spec_sha256(spec: dict[str, Any]) -> str:
    payload = {key: value for key, value in spec.items() if key != "run_spec_sha256"}
    return f"sha256:{hashlib.sha256(canonical_json(payload).encode()).hexdigest()}"


def resolve_run_unit(spec: dict[str, Any], run_unit_id: str) -> dict[str, Any]:
    validate_run_spec(spec)
    matches = [unit for unit in spec["units"] if unit["run_unit_id"] == run_unit_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one run unit for {run_unit_id!r}, found {len(matches)}")
    return matches[0]


def resolve_model_config(
    spec: dict[str, Any],
    unit: dict[str, Any],
    *,
    observed_model: str,
) -> dict[str, Any]:
    matches = [
        row
        for row in spec["model_configs"]
        if row["model_config_id"] == unit["model_config_id"]
        and row["canonical"]["requested_model"] == observed_model
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Observed model does not match run unit: "
            f"{observed_model!r}/{unit.get('model_config_id')!r}"
        )
    return matches[0]


def resolve_agent_policy(spec: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in spec["agent_policies"]
        if row["agent_policy_id"] == unit["agent_policy_id"]
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Run unit has no unique agent policy: {unit['run_unit_id']}")
    return matches[0]


def unit_matrix(unit: dict[str, Any]) -> tuple[list[str], list[int]]:
    return list(unit["task_ids"]), list(unit["rollout_seeds"])


def trajectory_id(
    spec: dict[str, Any],
    unit: dict[str, Any],
    *,
    task_id: str,
    rollout_seed: int,
) -> str:
    if task_id not in unit["task_ids"] or rollout_seed not in unit["rollout_seeds"]:
        raise RuntimeError(
            f"Task/seed is not registered in run unit {unit['run_unit_id']}: "
            f"{task_id}/{rollout_seed}"
        )
    return f"{spec['run_spec_id']}__{unit['run_unit_id']}__{task_id}__seed-{rollout_seed}"


def _unique_rows(value: Any, identifier_field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"run spec requires a {identifier_field.removesuffix('_id')} list")
    output: dict[str, dict[str, Any]] = {}
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"{identifier_field} rows must be objects")
        identifier = row.get(identifier_field)
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"row requires non-empty {identifier_field}")
        if identifier in output:
            raise ValueError(f"duplicate {identifier_field}: {identifier}")
        output[identifier] = row
    return output


def _positive_int(limits: dict[str, Any], field: str, unit_id: str) -> None:
    value = limits.get(field)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"run unit {unit_id} requires positive limits.{field}")

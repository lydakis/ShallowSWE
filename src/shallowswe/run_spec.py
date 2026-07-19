from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from .identity import agent_policy_id, canonical_json, model_config_id


RUN_SPEC_SCHEMA_VERSION = "shallowswe.run_spec.v0.1"
DEFAULT_EXECUTION_OPTIONS = {
    "n_jobs": 1,
    "row_timeout_seconds": 2700,
    "max_attempts": 2,
    "retry_delay_seconds": 15,
}


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
    _validate_execution_options(spec.get("execution_defaults", {}), "run spec")

    for identifier, config in model_configs.items():
        canonical = config.get("canonical")
        if not isinstance(canonical, dict):
            raise ValueError(f"model config {identifier} requires canonical identity")
        if identifier != model_config_id(canonical):
            raise ValueError(f"model_config_id does not match canonical identity: {identifier}")
        for field in ("requested_model", "expected_resolved_model"):
            if not isinstance(canonical.get(field), str) or not canonical[field]:
                raise ValueError(f"model config {identifier} requires canonical.{field}")
        sampling = canonical.get("sampling_config")
        if not isinstance(sampling, dict):
            raise ValueError(f"model config {identifier} requires canonical.sampling_config")
        temperature = sampling.get("temperature")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise ValueError(
                f"model config {identifier} requires numeric canonical.sampling_config.temperature"
            )

    for identifier, policy in agent_policies.items():
        canonical = policy.get("canonical")
        if not isinstance(canonical, dict):
            raise ValueError(f"agent policy {identifier} requires canonical identity")
        if identifier != agent_policy_id(canonical):
            raise ValueError(f"agent_policy_id does not match canonical identity: {identifier}")

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
        accounting = unit.get("accounting", {})
        if not isinstance(accounting, dict):
            raise ValueError(f"run unit {identifier} accounting must be an object")
        _validate_accounting(accounting, unit=unit, unit_id=identifier)
        _validate_execution_options(unit.get("execution", {}), f"run unit {identifier}")

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
        and observed_model
        in {
            row["canonical"]["requested_model"],
            row["canonical"].get("kaggle_model_slug"),
            row["canonical"].get("model_proxy_slug"),
        }
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


def validate_result_execution_identity(
    row: Any,
    spec: dict[str, Any],
    unit: dict[str, Any],
) -> None:
    """Validate observed execution identity without interpreting methodology metadata."""
    validate_run_spec(spec)
    model_rows = {
        entry["model_config_id"]: entry for entry in spec["model_configs"]
    }
    policy_rows = {
        entry["agent_policy_id"]: entry for entry in spec["agent_policies"]
    }
    model_entry = model_rows[unit["model_config_id"]]
    policy_entry = policy_rows[unit["agent_policy_id"]]
    model = model_entry["canonical"]
    policy = policy_entry["canonical"]
    mismatches = []
    expected = {
        "model": model.get("requested_model"),
        "requested_model": model.get("requested_model"),
        "resolved_model": model.get("expected_resolved_model"),
        "model_config_id": model_entry["model_config_id"],
        "model_config_canonical_json": model,
        "agent_policy_id": policy_entry["agent_policy_id"],
        "agent_policy_canonical_json": policy,
    }
    for field, expected_value in expected.items():
        observed_value = getattr(row, field, None)
        missing_resolution_for_zero_usage_exclusion = (
            field == "resolved_model"
            and observed_value is None
            and getattr(row, "status", None) == "excluded"
            and int(getattr(row, "input_tokens", 0) or 0) == 0
            and int(getattr(row, "output_tokens", 0) or 0) == 0
        )
        if observed_value != expected_value and not missing_resolution_for_zero_usage_exclusion:
            mismatches.append(field)
    for field in ("provider_route", "reasoning_effort"):
        if field in model and getattr(row, field, None) != model[field]:
            mismatches.append(field)
    sampling = model.get("sampling_config") or {}
    if "temperature" in sampling:
        observed_temperature = getattr(row, "temperature", None)
        if observed_temperature is None or abs(
            float(observed_temperature) - float(sampling["temperature"])
        ) > 1e-12:
            mismatches.append("temperature")
    if mismatches:
        raise ValueError(
            "result execution identity does not match RunSpec: "
            + ", ".join(sorted(mismatches))
        )


def resolve_execution_sampling(
    spec: dict[str, Any] | None,
    model_config: dict[str, Any] | None,
    *,
    fallback_temperature: float,
    fallback_task_suite_version: str,
) -> tuple[float, str]:
    if spec is None:
        if model_config is not None:
            raise RuntimeError("model configuration requires a run spec")
        return fallback_temperature, fallback_task_suite_version
    if model_config is None:
        raise RuntimeError("registered execution requires a model configuration")
    return (
        float(model_config["canonical"]["sampling_config"]["temperature"]),
        str(spec["task_suite_version"]),
    )


def unit_matrix(unit: dict[str, Any]) -> tuple[list[str], list[int]]:
    return list(unit["task_ids"]), list(unit["rollout_seeds"])


def resolve_execution_options(
    spec: dict[str, Any],
    unit: dict[str, Any],
) -> dict[str, int]:
    validate_run_spec(spec)
    options = dict(DEFAULT_EXECUTION_OPTIONS)
    options.update(spec.get("execution_defaults") or {})
    options.update(unit.get("execution") or {})
    return {field: int(options[field]) for field in DEFAULT_EXECUTION_OPTIONS}


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


def _validate_execution_options(value: Any, owner: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{owner} execution options must be an object")
    unknown = set(value) - set(DEFAULT_EXECUTION_OPTIONS)
    if unknown:
        raise ValueError(f"{owner} has unknown execution options: {sorted(unknown)}")
    for field in ("n_jobs", "row_timeout_seconds", "max_attempts"):
        configured = value.get(field)
        if configured is not None and (
            not isinstance(configured, int) or isinstance(configured, bool) or configured <= 0
        ):
            raise ValueError(f"{owner} requires positive execution option {field}")
    retry_delay = value.get("retry_delay_seconds")
    if retry_delay is not None and (
        not isinstance(retry_delay, int) or isinstance(retry_delay, bool) or retry_delay < 0
    ):
        raise ValueError(f"{owner} requires non-negative execution option retry_delay_seconds")


def _validate_accounting(
    accounting: dict[str, Any],
    *,
    unit: dict[str, Any],
    unit_id: str,
) -> None:
    if not accounting:
        return
    required_price_sheet = accounting.get("required_price_sheet_version")
    if required_price_sheet is not None and (
        not isinstance(required_price_sheet, str) or not required_price_sheet
    ):
        raise ValueError(
            f"run unit {unit_id} requires non-empty accounting.required_price_sheet_version"
        )
    task_contract_fields = (
        "expected_task_version",
        "expected_verifier_hash",
        "expected_environment_image_digest",
    )
    if any(accounting.get(field) is not None for field in task_contract_fields) and any(
        not isinstance(accounting.get(field), str) or not accounting[field]
        for field in task_contract_fields
    ):
        raise ValueError(
            f"run unit {unit_id} requires a complete expected task contract"
        )
    budget = accounting.get("reference_task_budget_usd")
    if budget is not None:
        if float(budget) <= 0:
            raise ValueError(f"run unit {unit_id} requires a positive reference task budget")
        if len(unit["task_ids"]) != 1:
            raise ValueError(
                f"run unit {unit_id} must bind one task when carrying a reference task budget"
            )
        runtime_cap = unit["limits"].get("dollar_usd")
        if runtime_cap is None or abs(float(runtime_cap) - float(budget)) > 1e-12:
            raise ValueError(
                f"run unit {unit_id} reference task budget must equal limits.dollar_usd"
            )
    for field in (
        "reference_anchor_replacement_cost_usd",
        "reference_anchor_replacement_cost_ci_low_usd",
        "reference_anchor_replacement_cost_ci_high_usd",
    ):
        value = accounting.get(field)
        if value is not None and float(value) < 0:
            raise ValueError(f"run unit {unit_id} requires non-negative accounting.{field}")
    attempts = accounting.get("anchor_confirmation_attempts")
    successes = accounting.get("anchor_confirmation_successes")
    if attempts is not None and (not isinstance(attempts, int) or attempts <= 0):
        raise ValueError(
            f"run unit {unit_id} requires positive accounting.anchor_confirmation_attempts"
        )
    if successes is not None and (
        not isinstance(successes, int)
        or successes < 0
        or attempts is None
        or successes > attempts
    ):
        raise ValueError(
            f"run unit {unit_id} has invalid accounting.anchor_confirmation_successes"
        )

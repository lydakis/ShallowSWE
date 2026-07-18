from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import hashlib
import json

from .identity import canonical_json
from .repair_policy import build_repair_policy
from .results import RepairLoopResult, aggregate_repair_loops, load_repair_loops
from .run_spec import (
    load_run_spec,
    run_spec_sha256,
    trajectory_id,
    validate_result_execution_identity,
    validate_run_spec,
)


ANALYSIS_BUNDLE_SCHEMA_VERSION = "shallowswe.analysis_bundle.v0.1"


def build_analysis_bundle(
    rows: Iterable[RepairLoopResult],
    methodology: dict[str, Any],
    *,
    scoring_run_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if methodology.get("schema_version") != "shallowswe.methodology_spec.v0.1":
        raise ValueError("unsupported methodology specification")
    all_rows = list(rows)
    row_selector = methodology.get("row_selector") or {}
    selected = [row for row in all_rows if _matches(row, row_selector)]
    if not selected:
        raise ValueError("methodology row_selector matched no results")
    requires_scoring_run_spec = methodology.get("repair_policy_row_selector") is not None
    if requires_scoring_run_spec and scoring_run_spec is None:
        raise ValueError("scoring RunSpec is required for final candidate analysis")
    scoring_run_spec_hash = (
        _validate_scoring_matrix(selected, scoring_run_spec)
        if scoring_run_spec is not None
        else None
    )
    group_by = tuple(
        str(value)
        for value in methodology.get("group_by", ["model_config_id", "agent_policy_id"])
    )
    payload: dict[str, Any] = {
        "schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION,
        "methodology_spec_id": methodology.get("methodology_spec_id"),
        "selected_rows": len(selected),
        "group_by": list(group_by),
        "aggregate": aggregate_repair_loops(selected, group_by=group_by),
    }
    if scoring_run_spec is not None:
        payload["scoring_run_spec_id"] = scoring_run_spec["run_spec_id"]
        payload["scoring_run_spec_sha256"] = scoring_run_spec_hash
    if methodology.get("select_repair_policy"):
        repair_policy_selector = methodology.get("repair_policy_row_selector")
        if repair_policy_selector is None:
            repair_policy_selector = row_selector
        repair_policy_rows = [
            row for row in all_rows if _matches(row, repair_policy_selector)
        ]
        if not repair_policy_rows:
            raise ValueError("methodology repair_policy_row_selector matched no results")
        payload["repair_policy_selected_rows"] = len(repair_policy_rows)
        repair_policy = build_repair_policy(
            repair_policy_rows,
            methodology,
        )
        payload["repair_policy"] = repair_policy
        if methodology.get("repair_policy_row_selector") is not None:
            payload["replacement_costs_sha256"] = _validate_scoring_artifact_bindings(
                selected,
                repair_policy,
            )
    payload["analysis_bundle_sha256"] = (
        f"sha256:{hashlib.sha256(canonical_json(payload).encode()).hexdigest()}"
    )
    return payload


def write_analysis_bundle(
    rows_path: Path,
    methodology_path: Path,
    output_path: Path,
    *,
    scoring_run_spec_path: Path | None = None,
) -> dict[str, Any]:
    report = build_analysis_bundle(
        load_repair_loops(rows_path),
        json.loads(methodology_path.read_text()),
        scoring_run_spec=(
            load_run_spec(scoring_run_spec_path)
            if scoring_run_spec_path is not None
            else None
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _matches(row: RepairLoopResult, selector: dict[str, Any]) -> bool:
    for key, expected in selector.items():
        if key.startswith("metadata."):
            actual = (row.run_metadata or {}).get(key.removeprefix("metadata."))
        else:
            if not hasattr(row, key):
                raise ValueError(f"unknown row_selector field: {key}")
            actual = getattr(row, key)
        allowed = expected if isinstance(expected, list) else [expected]
        if actual not in allowed:
            return False
    return True


def _validate_scoring_artifact_bindings(
    rows: Iterable[RepairLoopResult],
    repair_policy: dict[str, Any],
) -> str:
    repair_policy_hash = repair_policy.get("repair_policy_sha256")
    if not isinstance(repair_policy_hash, str) or not repair_policy_hash:
        raise ValueError("selected repair policy lacks a content hash")

    reference_budget_versions = {row.reference_budget_version for row in rows}
    metadata_policy_hashes = {
        (row.run_metadata or {}).get("repair_policy_sha256") for row in rows
    }
    if reference_budget_versions != {repair_policy_hash} or metadata_policy_hashes != {
        repair_policy_hash
    }:
        raise ValueError("candidate scoring rows do not match the selected repair policy")

    replacement_cost_hashes = {
        (row.run_metadata or {}).get("replacement_costs_sha256") for row in rows
    }
    if len(replacement_cost_hashes) != 1:
        raise ValueError("candidate scoring rows require one replacement-cost artifact")
    replacement_cost_hash = next(iter(replacement_cost_hashes))
    if not isinstance(replacement_cost_hash, str) or not replacement_cost_hash:
        raise ValueError("candidate scoring rows require one replacement-cost artifact")
    return replacement_cost_hash


def _validate_scoring_matrix(
    rows: list[RepairLoopResult],
    scoring_run_spec: dict[str, Any],
) -> str:
    validate_run_spec(scoring_run_spec)
    model_configs = {
        row["model_config_id"]: row["canonical"]
        for row in scoring_run_spec["model_configs"]
    }
    agent_policies = {
        row["agent_policy_id"]: row["canonical"]
        for row in scoring_run_spec["agent_policies"]
    }
    expected: dict[str, tuple[dict[str, Any], str, int]] = {}
    for unit in scoring_run_spec["units"]:
        for task_id in unit["task_ids"]:
            for seed in unit["rollout_seeds"]:
                identifier = trajectory_id(
                    scoring_run_spec,
                    unit,
                    task_id=task_id,
                    rollout_seed=seed,
                )
                expected[identifier] = (unit, task_id, seed)

    observed: set[str] = set()
    for row in rows:
        identifier = row.trajectory_id
        if not isinstance(identifier, str) or identifier not in expected:
            raise ValueError("candidate row does not match the exact scoring RunSpec")
        if identifier in observed:
            raise ValueError(f"duplicate scoring trajectory: {identifier}")
        observed.add(identifier)
        unit, task_id, seed = expected[identifier]
        validate_result_execution_identity(row, scoring_run_spec, unit)
        if (
            row.run_spec_id != scoring_run_spec["run_spec_id"]
            or row.run_unit_id != unit["run_unit_id"]
            or row.experiment_id != scoring_run_spec["experiment_id"]
            or row.task_suite_version != scoring_run_spec["task_suite_version"]
            or row.task_id != task_id
            or row.seed != seed
            or row.model_config_id != unit["model_config_id"]
            or row.model_config_canonical_json
            != model_configs[unit["model_config_id"]]
            or row.agent_policy_id != unit["agent_policy_id"]
            or row.agent_policy_canonical_json
            != agent_policies[unit["agent_policy_id"]]
            or row.verifier_submission_cap != unit["limits"]["verifier_submissions"]
            or row.agent_step_cap != unit["limits"]["agent_steps"]
            or (row.run_metadata or {}) != (unit.get("metadata") or {})
            or not _matches_scoring_accounting(row, unit.get("accounting") or {})
        ):
            raise ValueError(
                f"candidate trajectory {identifier} does not match the exact scoring RunSpec"
            )

    missing = sorted(set(expected) - observed)
    if missing:
        raise ValueError(
            "incomplete scoring matrix: "
            f"missing={len(missing)}, observed={len(observed)}, expected={len(expected)}"
        )
    return run_spec_sha256(scoring_run_spec)


def _matches_scoring_accounting(
    row: RepairLoopResult,
    accounting: dict[str, Any],
) -> bool:
    mappings = {
        "reference_task_budget_usd": "reference_task_budget_usd",
        "reference_budget_version": "reference_budget_version",
        "reference_budget_band": "reference_budget_band",
        "reference_budget_coverage_target": "reference_budget_coverage_target",
        "reference_budget_proposal_attempts": (
            "reference_budget_proposal_attempts"
        ),
        "reference_budget_development_check_attempts": (
            "reference_budget_development_check_attempts"
        ),
        "reference_budget_band_bumps": "reference_budget_band_bumps",
        "primary_anchor_model_config_id": "primary_anchor_model_config_id",
        "reference_anchor_replacement_cost_usd": (
            "reference_anchor_replacement_cost_usd"
        ),
        "anchor_price_sheet_version": "anchor_price_sheet_version",
        "anchor_confirmation_attempts": "anchor_confirmation_attempts",
        "anchor_confirmation_successes": "anchor_confirmation_successes",
        "pressure_band": "pressure_band",
        "required_price_sheet_version": "price_sheet_version",
        "expected_task_version": "task_version",
        "expected_verifier_hash": "verifier_hash",
        "expected_environment_image_digest": "environment_image_digest",
    }
    return all(
        accounting.get(accounting_field) == getattr(row, row_field)
        for accounting_field, row_field in mappings.items()
        if accounting_field in accounting
    )

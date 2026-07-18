from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import os
import tempfile

from .identity import canonical_json, model_config_id
from .results import RepairLoopResult
from .run_spec import (
    run_spec_sha256,
    validate_result_execution_identity,
    validate_run_spec,
)


REPLACEMENT_COSTS_SCHEMA_VERSION = "shallowswe.anchor_replacement_costs.v0.1"
SCORING_PANEL_SCHEMA_VERSION = "shallowswe.scoring_panel.v0.1"
_TASK_CONTRACT_FIELDS = (
    "task_version",
    "verifier_hash",
    "environment_image_digest",
)


def build_confirmation_run_spec(
    base_run_spec: dict[str, Any],
    repair_policy: dict[str, Any],
    methodology: dict[str, Any],
    *,
    run_spec_id: str,
    seed_start: int,
) -> dict[str, Any]:
    validate_run_spec(base_run_spec)
    _validate_transition_inputs(repair_policy, methodology)
    if not run_spec_id:
        raise ValueError("confirmation run_spec_id must not be empty")
    if seed_start < 0:
        raise ValueError("confirmation seed_start must be non-negative")

    anchor_id = _anchor_id(methodology)
    anchor_config, agent_policy, runner, wall_time = _anchor_execution_template(
        base_run_spec,
        anchor_id,
    )
    selected = repair_policy["selected_policy"]
    task_ids, attempts = _confirmation_sampling(methodology)
    budgets = _task_budget_index(repair_policy, expected_tasks=task_ids)
    contracts = _task_contract_index(repair_policy, expected_tasks=task_ids)
    pressures = _pressure_assignments(repair_policy, methodology, expected_tasks=task_ids)
    seeds = list(range(seed_start, seed_start + attempts))
    if set(seeds) & _run_spec_seeds(base_run_spec):
        raise ValueError("confirmation rollout seeds overlap permissive calibration seeds")

    units = []
    for task_id in task_ids:
        budget = budgets[task_id]
        units.append(
            {
                "run_unit_id": f"anchor-confirmation-{task_id}",
                "runner": runner,
                "kaggle_task_name": f"shallowswe-confirm-{task_id}",
                "model_config_id": anchor_id,
                "agent_policy_id": agent_policy["agent_policy_id"],
                "task_ids": [task_id],
                "rollout_seeds": seeds,
                "limits": {
                    "verifier_submissions": int(selected["verifier_submission_cap"]),
                    "agent_steps": int(selected["agent_step_cap"]),
                    "dollar_usd": float(budget["selected_budget_usd"]),
                    "wall_time_seconds": wall_time,
                },
                "accounting": _task_accounting(
                    budget,
                    repair_policy,
                    methodology,
                    primary_anchor_model_config_id=anchor_id,
                    pressure_band=pressures[task_id],
                    task_contract=contracts[task_id],
                ),
                "metadata": {
                    "phase": "anchor_confirmation",
                    "cohort": "anchor_confirmation",
                    "model_role": "primary_anchor",
                    "require_canonical_spend": True,
                },
            }
        )
    spec = {
        "schema_version": "shallowswe.run_spec.v0.1",
        "run_spec_id": run_spec_id,
        "experiment_id": base_run_spec["experiment_id"],
        "task_suite_version": base_run_spec["task_suite_version"],
        "model_configs": [anchor_config],
        "agent_policies": [agent_policy],
        "units": units,
    }
    spec["run_spec_sha256"] = run_spec_sha256(spec)
    validate_run_spec(spec)
    return spec


def build_anchor_replacement_costs(
    rows: Iterable[RepairLoopResult],
    repair_policy: dict[str, Any],
    methodology: dict[str, Any],
    *,
    base_run_spec: dict[str, Any],
    confirmation_run_spec: dict[str, Any],
) -> dict[str, Any]:
    _validate_transition_inputs(repair_policy, methodology)
    confirmation_units = _exact_confirmation_units(
        base_run_spec,
        confirmation_run_spec,
        repair_policy,
        methodology,
    )
    anchor_id = _anchor_id(methodology)
    task_ids, expected_attempts = _confirmation_sampling(methodology)
    minimum_successes = int(
        (methodology.get("selection_policy") or {}).get(
            "confirmation_minimum_successes",
            expected_attempts,
        )
    )
    budgets = _task_budget_index(repair_policy, expected_tasks=task_ids)
    expected_contracts = _task_contract_index(repair_policy, expected_tasks=task_ids)
    selected = repair_policy["selected_policy"]
    confirmation = [
        row
        for row in rows
        if (row.run_metadata or {}).get("phase") == "anchor_confirmation"
        and row.model_config_id == anchor_id
    ]
    run_spec_ids = {row.run_spec_id for row in confirmation}
    if None in run_spec_ids or len(run_spec_ids) != 1:
        raise ValueError("confirmation results require one complete RunSpec identity")
    agent_policy_ids = {row.agent_policy_id for row in confirmation}
    if None in agent_policy_ids or len(agent_policy_ids) != 1:
        raise ValueError("confirmation results require one agent-policy identity")
    confirmation_run_spec_id = str(next(iter(run_spec_ids)))
    confirmation_agent_policy_id = str(next(iter(agent_policy_ids)))
    if confirmation_run_spec_id != confirmation_run_spec["run_spec_id"]:
        raise ValueError("confirmation results do not match the exact confirmation RunSpec")
    by_task: dict[str, list[RepairLoopResult]] = defaultdict(list)
    for row in confirmation:
        by_task[row.task_id].append(row)
    if set(by_task) != set(task_ids):
        raise ValueError("confirmation results do not cover the declared task set")

    price_versions = {row.price_sheet_version for row in confirmation}
    if None in price_versions or len(price_versions) != 1:
        raise ValueError("confirmation results require one complete price-sheet identity")
    price_sheet_version = str(next(iter(price_versions)))
    if price_sheet_version != repair_policy.get("price_sheet_version"):
        raise ValueError("confirmation results do not use the repair-policy price sheet")
    task_results = []
    for task_id in task_ids:
        task_rows = by_task[task_id]
        expected_unit = confirmation_units[task_id]
        if len(task_rows) != expected_attempts or any(not row.is_scored for row in task_rows):
            raise ValueError(
                f"confirmation task {task_id} requires {expected_attempts} scored attempts"
            )
        for row in task_rows:
            validate_result_execution_identity(
                row,
                confirmation_run_spec,
                expected_unit,
            )
        replicate_ids = {row.seed if row.seed is not None else row.loop for row in task_rows}
        if len(replicate_ids) != expected_attempts:
            raise ValueError(f"confirmation task {task_id} contains duplicate replicates")
        if (
            replicate_ids != set(expected_unit["rollout_seeds"])
            or any(
                row.run_unit_id != expected_unit["run_unit_id"]
                or row.experiment_id != confirmation_run_spec["experiment_id"]
                or row.task_suite_version
                != confirmation_run_spec["task_suite_version"]
                or row.agent_policy_id != expected_unit["agent_policy_id"]
                for row in task_rows
            )
        ):
            raise ValueError(
                f"confirmation task {task_id} does not match the exact confirmation RunSpec"
            )
        observed_contracts = {
            (row.task_version, row.verifier_hash, row.environment_image_digest)
            for row in task_rows
        }
        if len(observed_contracts) != 1 or any(
            value is None for value in next(iter(observed_contracts))
        ):
            raise ValueError(f"confirmation task {task_id} lacks one immutable task contract")
        observed_contract = next(iter(observed_contracts))
        expected_contract = expected_contracts[task_id]
        if observed_contract != (
            expected_contract["task_version"],
            expected_contract["verifier_hash"],
            expected_contract["environment_image_digest"],
        ):
            raise ValueError(
                f"confirmation task {task_id} task contract does not match calibration"
            )
        budget = float(budgets[task_id]["selected_budget_usd"])
        if any(
            row.verifier_submission_cap != int(selected["verifier_submission_cap"])
            or row.agent_step_cap != int(selected["agent_step_cap"])
            or row.reference_task_budget_usd is None
            or abs(float(row.reference_task_budget_usd) - budget) > 1e-12
            or row.reference_budget_version != repair_policy.get("repair_policy_sha256")
            or row.primary_anchor_model_config_id != anchor_id
            for row in task_rows
        ):
            raise ValueError(f"confirmation task {task_id} does not use the frozen policy")
        spends = [row.canonical_list_price_equivalent_spend_usd for row in task_rows]
        if any(value is None for value in spends):
            raise ValueError(f"confirmation task {task_id} lacks canonical spend")
        total_spend = sum(float(value) for value in spends if value is not None)
        successes = sum(1 for row in task_rows if row.passed)
        replacement_cost = total_spend / successes if successes else None
        task_results.append(
            {
                "task_id": task_id,
                "task_version": expected_contract["task_version"],
                "verifier_hash": expected_contract["verifier_hash"],
                "environment_image_digest": expected_contract[
                    "environment_image_digest"
                ],
                "rollout_seeds": sorted(int(value) for value in replicate_ids),
                "attempts": len(task_rows),
                "successes": successes,
                "minimum_successes": minimum_successes,
                "confirmed": successes >= minimum_successes,
                "total_fresh_anchor_spend_usd": total_spend,
                "replacement_cost_usd": replacement_cost,
                "estimation_status": (
                    "estimated" if replacement_cost is not None else "no_anchor_successes"
                ),
            }
        )
    payload = {
        "schema_version": REPLACEMENT_COSTS_SCHEMA_VERSION,
        "methodology_spec_id": methodology.get("methodology_spec_id"),
        "repair_policy_sha256": repair_policy.get("repair_policy_sha256"),
        "primary_anchor_model_config_id": anchor_id,
        "confirmation_run_spec_id": confirmation_run_spec_id,
        "confirmation_run_spec_sha256": confirmation_run_spec[
            "run_spec_sha256"
        ],
        "confirmation_agent_policy_id": confirmation_agent_policy_id,
        "price_sheet_version": price_sheet_version,
        "tasks": task_results,
    }
    payload["replacement_costs_sha256"] = _artifact_hash(payload)
    return payload


def _exact_confirmation_units(
    base_run_spec: dict[str, Any],
    confirmation_run_spec: dict[str, Any],
    repair_policy: dict[str, Any],
    methodology: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    validate_run_spec(base_run_spec)
    validate_run_spec(confirmation_run_spec)
    task_ids, attempts = _confirmation_sampling(methodology)
    units = confirmation_run_spec.get("units")
    if not isinstance(units, list) or len(units) != len(task_ids):
        raise ValueError("confirmation RunSpec is not the exact frozen task matrix")
    seed_sets = [unit.get("rollout_seeds") for unit in units]
    if any(
        not isinstance(seeds, list)
        or len(seeds) != attempts
        or any(not isinstance(seed, int) or seed < 0 for seed in seeds)
        for seeds in seed_sets
    ):
        raise ValueError("confirmation RunSpec is not the exact frozen task matrix")
    first_seeds = list(seed_sets[0])
    if any(seeds != first_seeds for seeds in seed_sets[1:]):
        raise ValueError("confirmation RunSpec is not the exact frozen task matrix")
    seed_start = min(first_seeds)
    expected = build_confirmation_run_spec(
        base_run_spec,
        repair_policy,
        methodology,
        run_spec_id=str(confirmation_run_spec["run_spec_id"]),
        seed_start=seed_start,
    )
    if canonical_json(expected) != canonical_json(confirmation_run_spec):
        raise ValueError("confirmation RunSpec is not the exact frozen task matrix")
    return {
        str(unit["task_ids"][0]): unit
        for unit in confirmation_run_spec["units"]
    }


def build_scoring_run_spec(
    base_run_spec: dict[str, Any],
    panel: dict[str, Any],
    repair_policy: dict[str, Any],
    replacement_costs: dict[str, Any],
    methodology: dict[str, Any],
) -> dict[str, Any]:
    validate_run_spec(base_run_spec)
    _validate_transition_inputs(repair_policy, methodology)
    if panel.get("schema_version") != SCORING_PANEL_SCHEMA_VERSION:
        raise ValueError("unsupported scoring-panel schema")
    if replacement_costs.get("schema_version") != REPLACEMENT_COSTS_SCHEMA_VERSION:
        raise ValueError("unsupported replacement-cost schema")
    if replacement_costs.get("replacement_costs_sha256") != _artifact_hash(
        replacement_costs,
        hash_field="replacement_costs_sha256",
    ):
        raise ValueError("replacement_costs_sha256 does not match replacement costs")
    if replacement_costs.get("repair_policy_sha256") != repair_policy.get(
        "repair_policy_sha256"
    ):
        raise ValueError("replacement costs do not match the repair policy")
    if replacement_costs.get("methodology_spec_id") != methodology.get(
        "methodology_spec_id"
    ):
        raise ValueError("replacement costs methodology_spec_id does not match methodology")

    anchor_id = _anchor_id(methodology)
    if replacement_costs.get("primary_anchor_model_config_id") != anchor_id:
        raise ValueError("replacement costs do not match the primary anchor")
    _, agent_policy, runner, default_wall_time = _anchor_execution_template(
        base_run_spec,
        anchor_id,
    )
    if replacement_costs.get("confirmation_agent_policy_id") != agent_policy.get(
        "agent_policy_id"
    ):
        raise ValueError("replacement costs do not match the scoring agent policy")
    task_ids, _ = _confirmation_sampling(methodology)
    budgets = _task_budget_index(repair_policy, expected_tasks=task_ids)
    contracts = _task_contract_index(repair_policy, expected_tasks=task_ids)
    pressures = _pressure_assignments(repair_policy, methodology, expected_tasks=task_ids)
    replacement_by_task = {
        str(row["task_id"]): row for row in replacement_costs.get("tasks", [])
    }
    if set(replacement_by_task) != set(task_ids):
        raise ValueError("replacement-cost artifact does not cover the declared task set")
    confirmation_seed_sets: list[set[int]] = []
    for task_id, replacement in replacement_by_task.items():
        contract = contracts[task_id]
        if any(replacement.get(field) != contract[field] for field in _TASK_CONTRACT_FIELDS):
            raise ValueError(
                f"replacement-cost task {task_id} contract does not match repair policy"
            )
        confirmation_rollout_seeds = replacement.get("rollout_seeds")
        attempts = replacement.get("attempts")
        if (
            not isinstance(confirmation_rollout_seeds, list)
            or not isinstance(attempts, int)
            or len(confirmation_rollout_seeds) != attempts
            or any(
                not isinstance(seed, int) or seed < 0
                for seed in confirmation_rollout_seeds
            )
            or len(confirmation_rollout_seeds) != len(set(confirmation_rollout_seeds))
        ):
            raise ValueError(
                f"replacement-cost task {task_id} lacks valid confirmation rollout seeds"
            )
        confirmation_seed_sets.append(set(confirmation_rollout_seeds))
    if any(seed_set != confirmation_seed_sets[0] for seed_set in confirmation_seed_sets[1:]):
        raise ValueError("replacement costs contain inconsistent confirmation rollout seeds")

    model_rows = panel.get("model_configs")
    if not isinstance(model_rows, list) or not model_rows:
        raise ValueError("scoring panel requires model_configs")
    models = {}
    for row in model_rows:
        if not isinstance(row, dict) or not isinstance(row.get("canonical"), dict):
            raise ValueError("scoring-panel model rows require canonical identity")
        identifier = row.get("model_config_id")
        if identifier != model_config_id(row["canonical"]):
            raise ValueError("scoring-panel model_config_id does not match canonical identity")
        if identifier in models:
            raise ValueError(f"duplicate scoring-panel model_config_id: {identifier}")
        models[str(identifier)] = row
    roles = {str(role): str(identifier) for role, identifier in (panel.get("model_roles") or {}).items()}
    if not roles or len(roles) != len(models) or set(roles.values()) != set(models):
        raise ValueError("scoring-panel model_roles must identify every model config exactly once")
    seeds = panel.get("rollout_seeds")
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(not isinstance(seed, int) or seed < 0 for seed in seeds)
        or len(seeds) != len(set(seeds))
    ):
        raise ValueError("scoring panel requires unique non-negative rollout_seeds")
    scoring_seeds = set(seeds)
    if scoring_seeds & _run_spec_seeds(base_run_spec):
        raise ValueError("scoring rollout seeds overlap permissive calibration seeds")
    confirmation_seeds = confirmation_seed_sets[0]
    if scoring_seeds & confirmation_seeds:
        raise ValueError("scoring rollout seeds overlap fresh confirmation seeds")
    wall_time = int(panel.get("wall_time_seconds") or default_wall_time)
    selected = repair_policy["selected_policy"]
    confirmation_failure_action = _confirmation_failure_action(methodology)

    units = []
    for role, model_id in sorted(roles.items()):
        for task_id in task_ids:
            budget = budgets[task_id]
            replacement = replacement_by_task[task_id]
            confirmation_status = (
                "confirmed" if replacement.get("confirmed") else "confirmation_failed"
            )
            if (
                confirmation_status == "confirmation_failed"
                and confirmation_failure_action == "stop"
            ):
                raise ValueError(f"anchor confirmation did not accept task {task_id}")
            accounting = _task_accounting(
                budget,
                repair_policy,
                methodology,
                primary_anchor_model_config_id=anchor_id,
                pressure_band=pressures[task_id],
                task_contract=contracts[task_id],
            )
            accounting.update(
                {
                    "anchor_price_sheet_version": replacement_costs["price_sheet_version"],
                    "anchor_confirmation_attempts": int(replacement["attempts"]),
                    "anchor_confirmation_successes": int(replacement["successes"]),
                }
            )
            if replacement.get("replacement_cost_usd") is not None:
                accounting["reference_anchor_replacement_cost_usd"] = float(
                    replacement["replacement_cost_usd"]
                )
            units.append(
                {
                    "run_unit_id": f"score-{role}-{task_id}",
                    "runner": runner,
                    "kaggle_task_name": f"shallowswe-score-{role}-{task_id}",
                    "model_config_id": model_id,
                    "agent_policy_id": agent_policy["agent_policy_id"],
                    "task_ids": [task_id],
                    "rollout_seeds": list(seeds),
                    "limits": {
                        "verifier_submissions": int(selected["verifier_submission_cap"]),
                        "agent_steps": int(selected["agent_step_cap"]),
                        "dollar_usd": float(budget["selected_budget_usd"]),
                        "wall_time_seconds": wall_time,
                    },
                    "accounting": accounting,
                    "metadata": {
                        "phase": "candidate_scoring",
                        "cohort": "candidate_panel",
                        "model_role": role,
                        "require_canonical_spend": True,
                        "repair_policy_sha256": repair_policy["repair_policy_sha256"],
                        "replacement_costs_sha256": replacement_costs[
                            "replacement_costs_sha256"
                        ],
                        "anchor_confirmation_status": confirmation_status,
                    },
                }
            )
    spec = {
        "schema_version": "shallowswe.run_spec.v0.1",
        "run_spec_id": str(panel.get("run_spec_id") or ""),
        "experiment_id": base_run_spec["experiment_id"],
        "task_suite_version": base_run_spec["task_suite_version"],
        "model_configs": list(models.values()),
        "agent_policies": [agent_policy],
        "units": units,
    }
    spec["run_spec_sha256"] = run_spec_sha256(spec)
    validate_run_spec(spec)
    return spec


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(json.dumps(payload, indent=2) + "\n")
    os.replace(temporary, path)


def _validate_transition_inputs(
    repair_policy: dict[str, Any],
    methodology: dict[str, Any],
) -> None:
    if repair_policy.get("schema_version") != "shallowswe.repair_policy.v0.1":
        raise ValueError("unsupported repair-policy schema")
    if methodology.get("schema_version") != "shallowswe.methodology_spec.v0.1":
        raise ValueError("unsupported methodology specification")
    methodology_id = methodology.get("methodology_spec_id")
    if not isinstance(methodology_id, str) or not methodology_id:
        raise ValueError("methodology requires a non-empty methodology_spec_id")
    if repair_policy.get("methodology_spec_id") != methodology_id:
        raise ValueError("repair policy methodology_spec_id does not match methodology")
    selected = repair_policy.get("selected_policy")
    if not isinstance(selected, dict):
        raise ValueError("repair policy lacks selected_policy")
    for field in ("verifier_submission_cap", "agent_step_cap"):
        value = selected.get(field)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"repair policy requires positive selected_policy.{field}")
    expected_policy_hash = _artifact_hash(
        repair_policy,
        hash_field="repair_policy_sha256",
    )
    if repair_policy.get("repair_policy_sha256") != expected_policy_hash:
        raise ValueError("repair_policy_sha256 does not match repair policy")


def _anchor_id(methodology: dict[str, Any]) -> str:
    identifier = (methodology.get("model_roles") or {}).get("primary_anchor")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("methodology does not identify a primary anchor")
    return identifier


def _anchor_execution_template(
    base_run_spec: dict[str, Any],
    anchor_id: str,
) -> tuple[dict[str, Any], dict[str, Any], str, int]:
    configs = {
        str(row["model_config_id"]): row for row in base_run_spec["model_configs"]
    }
    if anchor_id not in configs:
        raise ValueError("base RunSpec does not contain the primary anchor")
    anchor_units = [
        unit for unit in base_run_spec["units"] if unit["model_config_id"] == anchor_id
    ]
    if not anchor_units:
        raise ValueError("base RunSpec has no primary-anchor execution unit")
    policy_ids = {str(unit["agent_policy_id"]) for unit in anchor_units}
    runners = {str(unit["runner"]) for unit in anchor_units}
    wall_times = {int(unit["limits"]["wall_time_seconds"]) for unit in anchor_units}
    if len(policy_ids) != 1 or len(runners) != 1 or len(wall_times) != 1:
        raise ValueError("primary-anchor execution template is not unique")
    policy_id = next(iter(policy_ids))
    policies = {
        str(row["agent_policy_id"]): row for row in base_run_spec["agent_policies"]
    }
    return (
        configs[anchor_id],
        policies[policy_id],
        next(iter(runners)),
        next(iter(wall_times)),
    )


def _confirmation_sampling(methodology: dict[str, Any]) -> tuple[list[str], int]:
    plan = (methodology.get("sampling") or {}).get("anchor_confirmation")
    if not isinstance(plan, dict):
        raise ValueError("methodology lacks anchor_confirmation sampling")
    task_ids = [str(task_id) for task_id in plan.get("task_ids", [])]
    attempts = int(plan.get("anchor_per_task") or 0)
    if not task_ids or len(task_ids) != len(set(task_ids)) or attempts <= 0:
        raise ValueError("invalid anchor_confirmation sampling")
    minimum_successes = int(
        (methodology.get("selection_policy") or {}).get(
            "confirmation_minimum_successes",
            attempts,
        )
    )
    if minimum_successes <= 0 or minimum_successes > attempts:
        raise ValueError("confirmation_minimum_successes must be within anchor attempts")
    return task_ids, attempts


def _confirmation_failure_action(methodology: dict[str, Any]) -> str:
    action = (methodology.get("selection_policy") or {}).get(
        "confirmation_failure_action",
        "stop",
    )
    if action not in {"stop", "continue_with_caveat"}:
        raise ValueError(
            "confirmation_failure_action must be stop or continue_with_caveat"
        )
    return str(action)


def _task_budget_index(
    repair_policy: dict[str, Any],
    *,
    expected_tasks: list[str],
) -> dict[str, dict[str, Any]]:
    budgets = {
        str(row["task_id"]): row
        for row in repair_policy.get("task_budgets", [])
        if isinstance(row, dict) and row.get("task_id")
    }
    if set(budgets) != set(expected_tasks):
        raise ValueError("repair policy task budgets do not cover the declared task set")
    if any(row.get("selected_budget_usd") is None for row in budgets.values()):
        raise ValueError("repair policy contains an unidentified task budget")
    return budgets


def _task_contract_index(
    repair_policy: dict[str, Any],
    *,
    expected_tasks: list[str],
) -> dict[str, dict[str, str]]:
    contracts: dict[str, dict[str, str]] = {}
    for row in repair_policy.get("task_contracts", []):
        if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
            raise ValueError("repair policy contains an invalid task contract")
        task_id = str(row["task_id"])
        if task_id in contracts:
            raise ValueError(f"repair policy contains duplicate task contract {task_id}")
        if any(not isinstance(row.get(field), str) or not row[field] for field in _TASK_CONTRACT_FIELDS):
            raise ValueError(f"repair policy task {task_id} has an incomplete task contract")
        contracts[task_id] = {
            field: str(row[field]) for field in _TASK_CONTRACT_FIELDS
        }
    if set(contracts) != set(expected_tasks):
        raise ValueError("repair policy task contracts do not cover the declared task set")
    return contracts


def _run_spec_seeds(run_spec: dict[str, Any]) -> set[int]:
    return {
        int(seed)
        for unit in run_spec.get("units", [])
        for seed in unit.get("rollout_seeds", [])
    }


def _pressure_assignments(
    repair_policy: dict[str, Any],
    methodology: dict[str, Any],
    *,
    expected_tasks: list[str],
) -> dict[str, str]:
    scheme = (methodology.get("selection_policy") or {}).get("pressure_taxonomy")
    if not isinstance(scheme, str) or not scheme:
        raise ValueError("methodology must select a pressure_taxonomy")
    taxonomy = (repair_policy.get("pressure_taxonomies") or {}).get(scheme)
    assignments = taxonomy.get("assignments") if isinstance(taxonomy, dict) else None
    if not isinstance(assignments, dict) or set(assignments) != set(expected_tasks):
        raise ValueError("selected pressure taxonomy does not cover the declared task set")
    return {str(task_id): str(label) for task_id, label in assignments.items()}


def _task_accounting(
    budget: dict[str, Any],
    repair_policy: dict[str, Any],
    methodology: dict[str, Any],
    *,
    primary_anchor_model_config_id: str,
    pressure_band: str,
    task_contract: dict[str, str],
) -> dict[str, Any]:
    permissive = (methodology.get("sampling") or {}).get("permissive_collection") or {}
    selection = methodology.get("selection_policy") or {}
    selected_budget = float(budget["selected_budget_usd"])
    return {
        "reference_task_budget_usd": selected_budget,
        "required_price_sheet_version": repair_policy.get("price_sheet_version"),
        "reference_budget_version": repair_policy.get("repair_policy_sha256"),
        "reference_budget_band": f"{selected_budget:g}",
        "reference_budget_coverage_target": selection.get(
            "selected_budget_check_coverage_target"
        ),
        "reference_budget_proposal_attempts": permissive.get(
            "anchor_proposal_per_task"
        ),
        "reference_budget_development_check_attempts": permissive.get(
            "anchor_budget_check_per_task"
        ),
        "reference_budget_band_bumps": int(budget.get("budget_band_bumps") or 0),
        "primary_anchor_model_config_id": primary_anchor_model_config_id,
        "pressure_band": pressure_band,
        "expected_task_version": task_contract["task_version"],
        "expected_verifier_hash": task_contract["verifier_hash"],
        "expected_environment_image_digest": task_contract[
            "environment_image_digest"
        ],
    }


def _artifact_hash(
    payload: dict[str, Any],
    *,
    hash_field: str | None = None,
) -> str:
    content = (
        {key: value for key, value in payload.items() if key != hash_field}
        if hash_field
        else payload
    )
    digest = hashlib.sha256(canonical_json(content).encode()).hexdigest()
    return f"sha256:{digest}"

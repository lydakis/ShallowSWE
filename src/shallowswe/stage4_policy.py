from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json

from .identity import canonical_json
from .results import RepairLoopResult, audit_repair_loop_evidence


STAGE4_POLICY_SCHEMA_VERSION = "shallowswe.stage4_policy.v0.1"


def build_stage4_policy(
    rows: Iterable[RepairLoopResult],
    manifest: dict[str, Any],
    *,
    evidence_class: str,
    release_class: str,
) -> dict[str, Any]:
    """Apply the preregistered Stage 4 truncation and budget-selection machinery.

    The caller must name the exact evidence and release classes. This makes a development
    rehearsal incapable of producing an official policy artifact by omission or default.
    """

    row_list = list(rows)
    if not row_list:
        raise ValueError("Stage 4 requires at least one repair-loop row")
    _require_exact_class(row_list, "evidence_class", evidence_class)
    _require_exact_class(row_list, "release_class", release_class)
    evidence_report = audit_repair_loop_evidence(
        row_list,
        group_by=("model_config_id", "agent_policy_id", "pilot_stage", "pilot_mode"),
    )
    if not evidence_report["valid"]:
        raise ValueError(
            "Stage 4 evidence is not internally poolable: "
            + ", ".join(str(issue) for issue in evidence_report["issues"])
        )

    development_proposal = (
        evidence_class == "development_dry_run" or release_class == "development_dry_run"
    )
    shadow_config_rows = manifest.get("development_shadow_model_configs", [])
    shadow_model_ids = {
        str(row.get("model_config_id"))
        for row in shadow_config_rows
        if isinstance(row, dict) and row.get("model_config_id")
    }
    uses_shadow_plan = development_proposal and any(
        row.model_config_id in shadow_model_ids for row in row_list
    )
    config_rows = (
        shadow_config_rows
        if uses_shadow_plan
        else manifest.get("model_configs", [])
    )
    configs = {
        str(config["role"]): str(config["model_config_id"])
        for config in config_rows
        if isinstance(config, dict)
        and config.get("role")
        and config.get("model_config_id")
        and config["role"] in {"primary_anchor", "floor_low", "floor_strong"}
    }
    anchor_id = configs.get("primary_anchor")
    if not anchor_id:
        raise ValueError("manifest does not identify the primary anchor")

    temporary = manifest.get("temporary_permissive_policy") or {}
    selection = manifest.get("stage4_selection_policy") or {}
    submission_candidates = _positive_sorted_ints(
        temporary.get("candidate_verifier_submission_caps"),
        "candidate_verifier_submission_caps",
    )
    step_candidates = _positive_sorted_ints(
        temporary.get("candidate_agent_step_caps"),
        "candidate_agent_step_caps",
    )
    budget_bands = _positive_sorted_floats(
        temporary.get("budget_bands_usd"),
        "budget_bands_usd",
    )
    capture_target = _probability(
        selection.get("success_capture_target"),
        "success_capture_target",
    )
    coverage_target = _probability(
        selection.get("selected_development_coverage_target"),
        "selected_development_coverage_target",
    )
    reported_coverage_targets = [
        _probability(value, "reported_budget_coverage_targets")
        for value in selection.get("reported_budget_coverage_targets", [])
    ]
    if not reported_coverage_targets:
        raise ValueError("reported_budget_coverage_targets must not be empty")
    max_bumps = int(selection.get("max_budget_band_bumps", -1))
    if max_bumps != 1:
        raise ValueError("Stage 4 pilot machinery requires exactly one allowed budget-band bump")

    stage3 = [
        row
        for row in row_list
        if row.pilot_stage == "permissive_collection" and row.is_scored
    ]
    anchor_rows = [row for row in stage3 if row.model_config_id == anchor_id]
    if not anchor_rows:
        raise ValueError("Stage 4 found no scored permissive primary-anchor rows")
    for row in stage3:
        _validated_verifier_checkpoints(row, require_canonical=_requires_canonical(row))
    trajectory_plan = (
        manifest.get("development_shadow_trajectory_plan")
        if uses_shadow_plan
        else manifest.get("trajectory_plan")
    )
    _require_permissive_matrix(
        stage3,
        task_ids=[str(task_id) for task_id in manifest.get("task_ids", [])],
        configs=configs,
        trajectory_plan=trajectory_plan,
    )
    _require_stable_task_contracts(row_list)

    submission_table = _capture_table(anchor_rows, submission_candidates)
    selected_k = _smallest_meeting_target(submission_table, capture_target)
    if selected_k is None:
        if not development_proposal:
            raise ValueError("no candidate verifier-submission cap meets the success-capture target")
        selected_k = max(submission_candidates)
        submission_selection_status = "selection_target_unmet"
    else:
        submission_selection_status = "target_met"
    step_table = _capture_table(anchor_rows, step_candidates, verifier_submission_cap=selected_k)
    selected_steps = _smallest_meeting_target(step_table, capture_target)
    if selected_steps is None:
        if not development_proposal:
            raise ValueError("no candidate agent-step cap meets the success-capture target")
        selected_steps = max(step_candidates)
        step_selection_status = "selection_target_unmet"
    else:
        step_selection_status = "target_met"

    task_budgets = _select_task_budgets(
        anchor_rows,
        budget_bands=budget_bands,
        coverage_target=coverage_target,
        reported_coverage_targets=reported_coverage_targets,
        verifier_submission_cap=selected_k,
        agent_step_cap=selected_steps,
        allow_fallback=development_proposal,
    )
    pressure = _pressure_diagnostics(
        stage3,
        configs=configs,
        verifier_submission_cap=selected_k,
        agent_step_cap=selected_steps,
    )
    _require_confirmation_matrix(
        row_list,
        anchor_id=anchor_id,
        trajectory_plan=trajectory_plan,
    )
    confirmation = _confirmation_diagnostics(
        row_list,
        anchor_id=anchor_id,
        task_budgets=task_budgets,
        verifier_submission_cap=selected_k,
        agent_step_cap=selected_steps,
        minimum_successes=int(selection.get("confirmation_minimum_successes", 7)),
        expected_attempts=int(selection.get("confirmation_attempts", 8)),
    )
    spend_bases = sorted({_row_spend_basis(row) for row in anchor_rows})
    policy_status = (
        "development_proposal"
        if development_proposal
        else "official_candidate_not_frozen"
    )
    payload: dict[str, Any] = {
        "schema_version": STAGE4_POLICY_SCHEMA_VERSION,
        "manifest": manifest.get("name"),
        "policy_status": policy_status,
        "evidence_class": evidence_class,
        "release_class": release_class,
        "spend_bases": spend_bases,
        "selection_constants": {
            "success_capture_target": capture_target,
            "selected_development_coverage_target": coverage_target,
            "reported_budget_coverage_targets": reported_coverage_targets,
            "max_budget_band_bumps": max_bumps,
        },
        "selected_policy": {
            "verifier_submission_cap": selected_k,
            "agent_step_cap": selected_steps,
            "verifier_submission_selection_status": submission_selection_status,
            "agent_step_selection_status": step_selection_status,
            "cap_disclosure": "undisclosed",
        },
        "submission_cap_diagnostics": submission_table,
        "step_cap_diagnostics": step_table,
        "task_budgets": task_budgets,
        "pressure_diagnostics": pressure,
        "pressure_taxonomies": _pressure_taxonomies(pressure),
        "confirmation_diagnostics": confirmation,
        "evidence_audit": evidence_report,
        "official_launch_eligible": False,
        "official_launch_blocker": (
            "development_evidence_cannot_freeze_official_policy"
            if policy_status == "development_proposal"
            else "official_policy_requires_explicit_freeze_after_review"
        ),
    }
    payload["stage4_policy_sha256"] = (
        f"sha256:{hashlib.sha256(canonical_json(payload).encode()).hexdigest()}"
    )
    return payload


def write_stage4_policy(
    rows_path: Path,
    manifest_path: Path,
    output_path: Path,
    *,
    evidence_class: str,
    release_class: str,
) -> dict[str, Any]:
    from .results import load_repair_loops

    report = build_stage4_policy(
        load_repair_loops(rows_path),
        json.loads(manifest_path.read_text()),
        evidence_class=evidence_class,
        release_class=release_class,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _capture_table(
    rows: list[RepairLoopResult],
    candidates: list[int],
    *,
    verifier_submission_cap: int | None = None,
) -> list[dict[str, Any]]:
    eventual = sum(1 for row in rows if _success_checkpoint(row) is not None)
    table = []
    for candidate in candidates:
        successes = sum(
            1
            for row in rows
            if _succeeds_within(
                row,
                verifier_submission_cap=(
                    candidate if verifier_submission_cap is None else verifier_submission_cap
                ),
                agent_step_cap=(candidate if verifier_submission_cap is not None else None),
            )
        )
        table.append(
            {
                "candidate": candidate,
                "captured_successes": successes,
                "eventual_successes": eventual,
                "success_capture_rate": successes / eventual if eventual else None,
            }
        )
    return table


def _require_permissive_matrix(
    rows: list[RepairLoopResult],
    *,
    task_ids: list[str],
    configs: dict[str, str],
    trajectory_plan: Any,
) -> None:
    if not task_ids or not isinstance(trajectory_plan, dict):
        return
    plan = trajectory_plan.get("permissive_collection")
    if not isinstance(plan, dict):
        return
    expected: Counter[tuple[str, str, str | None]] = Counter()
    for task_id in task_ids:
        expected[(task_id, "primary_anchor", "budget_proposal")] = int(
            plan.get("anchor_proposal_per_task") or 0
        )
        expected[(task_id, "primary_anchor", "development_check")] = int(
            plan.get("anchor_development_check_per_task") or 0
        )
        for role in ("floor_low", "floor_strong"):
            expected[(task_id, role, None)] = int(plan.get("each_floor_per_task") or 0)
    role_by_id = {identifier: role for role, identifier in configs.items()}
    actual: Counter[tuple[str, str, str | None]] = Counter()
    unknown = 0
    for row in rows:
        role = role_by_id.get(row.model_config_id)
        if role == "primary_anchor":
            key = (row.task_id, role, row.pilot_cohort)
        elif role in {"floor_low", "floor_strong"}:
            key = (row.task_id, role, None)
        else:
            unknown += 1
            continue
        actual[key] += 1
    if unknown or actual != expected:
        missing = sum((expected - actual).values())
        extra = sum((actual - expected).values()) + unknown
        raise ValueError(
            f"incomplete permissive matrix: missing={missing}, unexpected={extra}"
        )


def _require_confirmation_matrix(
    rows: list[RepairLoopResult],
    *,
    anchor_id: str,
    trajectory_plan: Any,
) -> None:
    observed = [row for row in rows if row.pilot_stage == "fresh_anchor_confirmation"]
    if not observed or not isinstance(trajectory_plan, dict):
        return
    plan = trajectory_plan.get("fresh_anchor_confirmation")
    if not isinstance(plan, dict):
        return
    task_ids = [str(value) for value in plan.get("task_ids", [])]
    expected_attempts = int(plan.get("anchor_per_task") or 0)
    actual = Counter(
        row.task_id
        for row in observed
        if row.is_scored and row.model_config_id == anchor_id
    )
    expected = Counter({task_id: expected_attempts for task_id in task_ids})
    if actual != expected or len(observed) != sum(expected.values()):
        raise ValueError("incomplete fresh-confirmation matrix")


def _smallest_meeting_target(table: list[dict[str, Any]], target: float) -> int | None:
    for row in table:
        rate = row["success_capture_rate"]
        if isinstance(rate, int | float) and rate >= target:
            return int(row["candidate"])
    return None


def _select_task_budgets(
    rows: list[RepairLoopResult],
    *,
    budget_bands: list[float],
    coverage_target: float,
    reported_coverage_targets: list[float],
    verifier_submission_cap: int,
    agent_step_cap: int,
    allow_fallback: bool,
) -> list[dict[str, Any]]:
    by_task: dict[str, list[RepairLoopResult]] = defaultdict(list)
    for row in rows:
        by_task[row.task_id].append(row)
    budgets = []
    for task_id, task_rows in sorted(by_task.items()):
        proposal = [row for row in task_rows if row.pilot_cohort == "budget_proposal"]
        development_check = [
            row for row in task_rows if row.pilot_cohort == "development_check"
        ]
        if not proposal or not development_check:
            raise ValueError(
                f"task {task_id} requires budget_proposal and development_check cohorts"
            )
        coverage_table = [
            {
                "budget_usd": band,
                "proposal_coverage": _coverage(
                    proposal,
                    band,
                    verifier_submission_cap=verifier_submission_cap,
                    agent_step_cap=agent_step_cap,
                ),
                "development_check_coverage": _coverage(
                    development_check,
                    band,
                    verifier_submission_cap=verifier_submission_cap,
                    agent_step_cap=agent_step_cap,
                ),
                "full_development_coverage": _coverage(
                    task_rows,
                    band,
                    verifier_submission_cap=verifier_submission_cap,
                    agent_step_cap=agent_step_cap,
                ),
            }
            for band in budget_bands
        ]
        proposal_index = next(
            (
                index
                for index, row in enumerate(coverage_table)
                if row["proposal_coverage"] >= coverage_target
            ),
            None,
        )
        if proposal_index is None:
            if not allow_fallback:
                raise ValueError(f"task {task_id} has no proposal budget meeting coverage")
            budgets.append(
                {
                    "task_id": task_id,
                    "proposal_budget_usd": None,
                    "selected_budget_usd": budget_bands[-1],
                    "budget_band_bumps": 0,
                    "development_check_passed": False,
                    "selection_status": "budget_not_identified",
                    "proposal_budget_by_coverage_target": {
                        str(target): next(
                            (
                                row["budget_usd"]
                                for row in coverage_table
                                if row["proposal_coverage"] >= target
                            ),
                            None,
                        )
                        for target in reported_coverage_targets
                    },
                    "coverage_table": coverage_table,
                }
            )
            continue
        selected_index = proposal_index
        if coverage_table[selected_index]["development_check_coverage"] < coverage_target:
            selected_index = min(selected_index + 1, len(coverage_table) - 1)
        within_schedule = selected_index < len(coverage_table)
        check_passed = (
            within_schedule
            and coverage_table[selected_index]["development_check_coverage"] >= coverage_target
        )
        budgets.append(
            {
                "task_id": task_id,
                "proposal_budget_usd": coverage_table[proposal_index]["budget_usd"],
                "selected_budget_usd": (
                    coverage_table[selected_index]["budget_usd"] if within_schedule else None
                ),
                "budget_band_bumps": selected_index - proposal_index if within_schedule else 1,
                "development_check_passed": check_passed,
                "selection_status": (
                    "development_confirmed" if check_passed else "development_check_failed"
                ),
                "proposal_budget_by_coverage_target": {
                    str(target): next(
                        (
                            row["budget_usd"]
                            for row in coverage_table
                            if row["proposal_coverage"] >= target
                        ),
                        None,
                    )
                    for target in reported_coverage_targets
                },
                "coverage_table": coverage_table,
            }
        )
    return budgets


def _pressure_diagnostics(
    rows: list[RepairLoopResult],
    *,
    configs: dict[str, str],
    verifier_submission_cap: int,
    agent_step_cap: int,
) -> list[dict[str, Any]]:
    role_by_id = {identifier: role for role, identifier in configs.items()}
    floor_rows = [
        row
        for row in rows
        if role_by_id.get(row.model_config_id) in {"floor_low", "floor_strong"}
    ]
    by_task_role: dict[tuple[str, str], list[RepairLoopResult]] = defaultdict(list)
    for row in floor_rows:
        role = role_by_id[str(row.model_config_id)]
        by_task_role[(row.task_id, role)].append(row)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (task_id, role), role_rows in sorted(by_task_role.items()):
        first = sum(1 for row in role_rows if _first_submit_passed(row)) / len(role_rows)
        eventual = sum(
            1
            for row in role_rows
            if _succeeds_within(
                row,
                verifier_submission_cap=verifier_submission_cap,
                agent_step_cap=agent_step_cap,
            )
        ) / len(role_rows)
        by_task[task_id].append(
            {
                "role": role,
                "attempts": len(role_rows),
                "first_submit_rate": first,
                "eventual_solve_rate": eventual,
            }
        )
    diagnostics = []
    for task_id, roles in sorted(by_task.items()):
        first_rates = [float(role["first_submit_rate"]) for role in roles]
        eventual_rates = [float(role["eventual_solve_rate"]) for role in roles]
        diagnostics.append(
            {
                "task_id": task_id,
                "floor_roles": roles,
                "floor_first_submit_rate_min": min(first_rates),
                "floor_first_submit_rate_max": max(first_rates),
                "floor_first_submit_rate_mean": sum(first_rates) / len(first_rates),
                "floor_first_submit_dispersion": max(first_rates) - min(first_rates),
                "floor_eventual_solve_rate_min": min(eventual_rates),
                "floor_eventual_solve_rate_max": max(eventual_rates),
                "selection_status": (
                    "pressure_not_identified"
                    if max(first_rates) - min(first_rates) <= 1e-12
                    else "descriptive_pressure_observed"
                ),
            }
        )
    return diagnostics


def _pressure_taxonomies(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    two_band = {}
    three_band = {}
    for row in diagnostics:
        rate = float(row["floor_first_submit_rate_mean"])
        task_id = str(row["task_id"])
        two_band[task_id] = "lower" if rate >= 0.5 else "elevated"
        three_band[task_id] = "low" if rate >= 0.75 else "medium" if rate >= 0.25 else "high"
    return {
        "two_band": {"assignments": two_band, "counts": _counts(two_band.values())},
        "three_band": {"assignments": three_band, "counts": _counts(three_band.values())},
        "selection_status": (
            "pressure_not_identified"
            if diagnostics
            and all(row["selection_status"] == "pressure_not_identified" for row in diagnostics)
            else "descriptive_only_requires_human_task_review"
        ),
    }


def _confirmation_diagnostics(
    rows: list[RepairLoopResult],
    *,
    anchor_id: str,
    task_budgets: list[dict[str, Any]],
    verifier_submission_cap: int,
    agent_step_cap: int,
    minimum_successes: int,
    expected_attempts: int,
) -> list[dict[str, Any]]:
    budget_by_task = {
        str(row["task_id"]): row["selected_budget_usd"]
        for row in task_budgets
        if row["selected_budget_usd"] is not None
    }
    confirmation = [
        row
        for row in rows
        if row.pilot_stage == "fresh_anchor_confirmation"
        and row.model_config_id == anchor_id
        and row.is_scored
    ]
    by_task: dict[str, list[RepairLoopResult]] = defaultdict(list)
    for row in confirmation:
        by_task[row.task_id].append(row)
    output = []
    for task_id, task_rows in sorted(by_task.items()):
        budget = budget_by_task.get(task_id)
        if any(row.verifier_submission_cap != verifier_submission_cap for row in task_rows):
            raise ValueError(f"confirmation task {task_id} does not use the selected K")
        if any(row.agent_step_cap != agent_step_cap for row in task_rows):
            raise ValueError(f"confirmation task {task_id} does not use the selected step guard")
        if budget is not None and any(
            row.reference_task_budget_usd is None
            or abs(float(row.reference_task_budget_usd) - budget) > 1e-12
            for row in task_rows
        ):
            raise ValueError(f"confirmation task {task_id} does not use the selected budget")
        successes = (
            sum(
                1
                for row in task_rows
                if _succeeds_within(
                    row,
                    verifier_submission_cap=verifier_submission_cap,
                    agent_step_cap=agent_step_cap,
                    budget_usd=budget,
                )
            )
            if budget is not None
            else 0
        )
        output.append(
            {
                "task_id": task_id,
                "attempts": len(task_rows),
                "expected_attempts": expected_attempts,
                "successes": successes,
                "minimum_successes": minimum_successes,
                "confirmed": len(task_rows) == expected_attempts and successes >= minimum_successes,
            }
        )
    return output


def _coverage(
    rows: list[RepairLoopResult],
    budget_usd: float,
    *,
    verifier_submission_cap: int,
    agent_step_cap: int,
) -> float:
    return sum(
        1
        for row in rows
        if _succeeds_within(
            row,
            verifier_submission_cap=verifier_submission_cap,
            agent_step_cap=agent_step_cap,
            budget_usd=budget_usd,
        )
    ) / len(rows)


def _succeeds_within(
    row: RepairLoopResult,
    *,
    verifier_submission_cap: int,
    agent_step_cap: int | None,
    budget_usd: float | None = None,
) -> bool:
    checkpoint = _success_checkpoint(row)
    if checkpoint is None:
        return False
    if int(checkpoint["verifier_submission"]) > verifier_submission_cap:
        return False
    if agent_step_cap is not None and int(checkpoint["cumulative_agent_steps"]) > agent_step_cap:
        return False
    spend = _checkpoint_spend(checkpoint)
    return budget_usd is None or (spend is not None and spend <= budget_usd + 1e-12)


def _first_submit_passed(row: RepairLoopResult) -> bool:
    return any(
        int(checkpoint["verifier_submission"]) == 1 and checkpoint["result_class"] == "passed"
        for checkpoint in _validated_verifier_checkpoints(
            row,
            require_canonical=_requires_canonical(row),
        )
    )


def _success_checkpoint(row: RepairLoopResult) -> dict[str, Any] | None:
    return next(
        (
            checkpoint
            for checkpoint in _validated_verifier_checkpoints(
                row,
                require_canonical=_requires_canonical(row),
            )
            if checkpoint["result_class"] == "passed"
        ),
        None,
    )


def _validated_verifier_checkpoints(
    row: RepairLoopResult,
    *,
    require_canonical: bool,
) -> list[dict[str, Any]]:
    checkpoints = [
        checkpoint
        for checkpoint in (row.event_checkpoints or [])
        if checkpoint.get("event_type") == "verifier_result"
    ]
    if len(checkpoints) != row.verifier_submissions:
        raise ValueError(
            f"row {row.task_id}/{row.loop} has incomplete per-submission checkpoints"
        )
    expected = list(range(1, len(checkpoints) + 1))
    actual = [int(checkpoint.get("verifier_submission") or 0) for checkpoint in checkpoints]
    if actual != expected:
        raise ValueError(f"row {row.task_id}/{row.loop} has non-contiguous verifier checkpoints")
    required = (
        "result_class",
        "cumulative_agent_steps",
        "cumulative_input_tokens",
        "cumulative_output_tokens",
    )
    if any(any(checkpoint.get(field) is None for field in required) for checkpoint in checkpoints):
        raise ValueError(f"row {row.task_id}/{row.loop} has incomplete checkpoint accounting")
    if require_canonical and any(
        checkpoint.get("cumulative_canonical_spend_usd") is None
        for checkpoint in checkpoints
    ):
        raise ValueError(
            f"official row {row.task_id}/{row.loop} lacks cumulative canonical spend"
        )
    if row.passed != any(checkpoint.get("result_class") == "passed" for checkpoint in checkpoints):
        raise ValueError(f"row {row.task_id}/{row.loop} pass state disagrees with checkpoints")
    return checkpoints


def _checkpoint_spend(checkpoint: dict[str, Any]) -> float | None:
    canonical = checkpoint.get("cumulative_canonical_spend_usd")
    if canonical is not None:
        return float(canonical)
    gateway = checkpoint.get("cumulative_gateway_reported_cost_usd")
    return float(gateway) if gateway is not None else None


def _row_spend_basis(row: RepairLoopResult) -> str:
    checkpoints = _validated_verifier_checkpoints(
        row,
        require_canonical=_requires_canonical(row),
    )
    return (
        "canonical_list_price_equivalent"
        if all(checkpoint.get("cumulative_canonical_spend_usd") is not None for checkpoint in checkpoints)
        else "gateway_reported_development_only"
    )


def _requires_canonical(row: RepairLoopResult) -> bool:
    return row.evidence_class == "official_pilot" or row.release_class == "protocol_validation"


def _require_stable_task_contracts(rows: list[RepairLoopResult]) -> None:
    by_model_task: dict[tuple[str | None, str], list[RepairLoopResult]] = defaultdict(list)
    for row in rows:
        by_model_task[(row.model_config_id, row.task_id)].append(row)
    for (_model_id, task_id), task_rows in by_model_task.items():
        for field in (
            "task_version",
            "verifier_hash",
            "environment_image_digest",
            "price_sheet_version",
            "routine_review_version",
        ):
            values = {getattr(row, field) for row in task_rows}
            if len(values) > 1:
                raise ValueError(f"Stage 4 task {task_id} has mixed {field}")


def _require_exact_class(rows: list[RepairLoopResult], field: str, expected: str) -> None:
    values = {getattr(row, field) for row in rows}
    if values != {expected}:
        raise ValueError(f"Stage 4 requires {field}={expected!r}; found {sorted(map(str, values))}")


def _positive_sorted_ints(value: Any, field: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result = sorted({int(item) for item in value})
    if not result or result[0] <= 0:
        raise ValueError(f"{field} must contain positive values")
    return result


def _positive_sorted_floats(value: Any, field: str) -> list[float]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result = sorted({float(item) for item in value})
    if not result or result[0] <= 0:
        raise ValueError(f"{field} must contain positive values")
    return result


def _probability(value: Any, field: str) -> float:
    result = float(value)
    if result <= 0 or result > 1:
        raise ValueError(f"{field} must be in (0, 1]")
    return result


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))

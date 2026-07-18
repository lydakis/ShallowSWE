from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .results import (
    PriceCatalog,
    RepairLoopResult,
    RolloutResult,
    aggregate_results,
    audit_repair_loop_evidence,
)
from .task_metadata import CATEGORY_ORDER, SIZE_ORDER


WORKLOAD_INDEX_SCHEMA_VERSION = "shallowswe.workload_index.v0.3"
REPAIR_LOOP_WORKLOAD_INDEX_SCHEMA_VERSION = "shallowswe.repair_loop_workload_index.v0.1"


def build_repair_loop_workload_index(
    rows: Iterable[RepairLoopResult],
    *,
    target_tasks_per_cell: int = 4,
    pressure_bands: tuple[str, ...] = ("low", "medium", "high"),
    evidence_class: str,
    release_class: str,
) -> dict[str, object]:
    """Build the v0.4.2 category-by-pressure weighted ratio for repair-loop rows."""

    if target_tasks_per_cell <= 0:
        raise ValueError("target_tasks_per_cell must be positive")
    if not pressure_bands or len(set(pressure_bands)) != len(pressure_bands):
        raise ValueError("pressure_bands must be a non-empty unique sequence")
    row_list = list(rows)
    if not row_list:
        raise ValueError("repair-loop workload index requires rows")
    if {row.evidence_class for row in row_list} != {evidence_class}:
        raise ValueError(f"workload evidence_class must be exactly {evidence_class!r}")
    if {row.release_class for row in row_list} != {release_class}:
        raise ValueError(f"workload release_class must be exactly {release_class!r}")
    evidence_report = audit_repair_loop_evidence(
        row_list,
        group_by=("model_config_id", "agent_policy_id"),
    )
    if not evidence_report["valid"]:
        raise ValueError(
            "repair-loop workload evidence is not poolable: "
            + ", ".join(str(issue) for issue in evidence_report["issues"])
        )
    invalid_pressure = sorted(
        {row.pressure_band for row in row_list if row.pressure_band not in pressure_bands},
        key=str,
    )
    if invalid_pressure:
        raise ValueError(f"rows contain unsupported pressure bands: {invalid_pressure}")
    task_contracts: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in row_list:
        task_contracts[row.task_id].add((row.category, str(row.pressure_band)))
    for task_id, contracts in sorted(task_contracts.items()):
        if len(contracts) > 1:
            categories = {category for category, _pressure in contracts}
            field = "category" if len(categories) > 1 else "pressure_band"
            raise ValueError(f"task {task_id} has mixed {field} across model cohorts")

    task_keys = sorted(
        {(row.category, str(row.pressure_band), row.task_id) for row in row_list},
        key=lambda value: (
            _category_rank(value[0]),
            pressure_bands.index(value[1]),
            value[2],
        ),
    )
    declared_task_weight = 1 / (
        len(CATEGORY_ORDER) * len(pressure_bands) * target_tasks_per_cell
    )
    observed_counts: dict[tuple[str, str], int] = defaultdict(int)
    for category, pressure, _task_id in task_keys:
        observed_counts[(category, pressure)] += 1
    overfilled = [
        f"{category}/{pressure}"
        for (category, pressure), count in observed_counts.items()
        if count > target_tasks_per_cell
    ]
    if overfilled:
        raise ValueError(
            "declared repair-loop basket has overfilled cells: " + ", ".join(overfilled)
        )
    underfilled_cells = [
        {
            "category": category,
            "pressure_band": pressure,
            "observed_tasks": observed_counts[(category, pressure)],
            "target_tasks": target_tasks_per_cell,
            "missing_tasks": max(
                0,
                target_tasks_per_cell - observed_counts[(category, pressure)],
            ),
        }
        for category in CATEGORY_ORDER
        for pressure in pressure_bands
        if observed_counts[(category, pressure)] < target_tasks_per_cell
    ]
    task_weights = [
        {
            "task_id": task_id,
            "category": category,
            "pressure_band": pressure,
            "declared_weight": declared_task_weight,
        }
        for category, pressure, task_id in task_keys
    ]
    declared_coverage_weight = min(1.0, len(task_keys) * declared_task_weight)

    grouped: dict[tuple[str, str, str], list[RepairLoopResult]] = defaultdict(list)
    for row in row_list:
        grouped[(str(row.model_config_id), str(row.agent_policy_id), row.task_id)].append(row)
    cells: list[dict[str, object]] = []
    for (model_id, policy_id, task_id), task_rows in sorted(grouped.items()):
        scored = [row for row in task_rows if row.is_scored]
        if not scored:
            continue
        successes = sum(1 for row in scored if row.passed)
        canonical = [row.canonical_list_price_equivalent_spend_usd for row in scored]
        realized_mean = (
            sum(float(value) for value in canonical if value is not None) / len(scored)
            if all(value is not None for value in canonical)
            else None
        )
        reference_charges = [
            (
                row.canonical_list_price_equivalent_spend_usd
                if row.passed
                else row.reference_task_budget_usd
            )
            for row in scored
        ]
        escalation_charges = [
            (
                float(row.canonical_list_price_equivalent_spend_usd or 0.0)
                + (0.0 if row.passed else float(row.reference_anchor_replacement_cost_usd or 0.0))
                if row.canonical_list_price_equivalent_spend_usd is not None
                and (row.passed or row.reference_anchor_replacement_cost_usd is not None)
                else None
            )
            for row in scored
        ]
        first = scored[0]
        cells.append(
            {
                "model_config_id": model_id,
                "agent_policy_id": policy_id,
                "model": first.model,
                "task_id": task_id,
                "category": first.category,
                "pressure_band": first.pressure_band,
                "attempts": len(scored),
                "excluded_attempts": len(task_rows) - len(scored),
                "successes": successes,
                "solve_rate": successes / len(scored),
                "mean_realized_charge_usd": realized_mean,
                "mean_reference_budget_charge_usd": _complete_mean(reference_charges),
                "mean_escalation_charge_usd": _complete_mean(escalation_charges),
                "declared_weight": declared_task_weight,
            }
        )

    model_groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for cell in cells:
        model_groups[(str(cell["model_config_id"]), str(cell["agent_policy_id"]))].append(cell)
    models = []
    for (model_id, policy_id), model_cells in sorted(model_groups.items()):
        coverage_weight = len(model_cells) * declared_task_weight
        weighted_success = _declared_weighted_sum(model_cells, "solve_rate")
        summary: dict[str, object] = {
            "model_config_id": model_id,
            "agent_policy_id": policy_id,
            "model": model_cells[0]["model"],
            "task_count": len(model_cells),
            "declared_coverage_weight": coverage_weight,
            "missing_declared_weight": max(0.0, 1.0 - coverage_weight),
            "weighted_solve_rate": (
                weighted_success if _weights_match(coverage_weight, 1.0) else None
            ),
            "partial_weighted_solve_rate": (
                weighted_success / coverage_weight
                if weighted_success is not None and coverage_weight > 0
                else None
            ),
        }
        for variant, charge_field in (
            ("reference_budget", "mean_reference_budget_charge_usd"),
            ("realized", "mean_realized_charge_usd"),
            ("escalation", "mean_escalation_charge_usd"),
        ):
            numerator = _declared_weighted_sum(model_cells, charge_field)
            denominator = weighted_success
            partial = _ratio_or_none(numerator, denominator)
            complete = _weights_match(coverage_weight, 1.0) and all(
                _is_number(cell.get(charge_field)) for cell in model_cells
            )
            summary[f"partial_basket_{variant}_cpsc"] = partial
            summary[f"basket_{variant}_cpsc"] = partial if complete else None
        models.append(summary)

    return {
        "schema_version": REPAIR_LOOP_WORKLOAD_INDEX_SCHEMA_VERSION,
        "evidence_class": evidence_class,
        "release_class": release_class,
        "weighting": {
            "scheme": "equal_category_equal_pressure_equal_declared_task",
            "categories": list(CATEGORY_ORDER),
            "pressure_bands": list(pressure_bands),
            "target_tasks_per_category_pressure": target_tasks_per_cell,
            "declared_task_weight": declared_task_weight,
            "declared_coverage_weight": declared_coverage_weight,
            "partial_basket": not _weights_match(declared_coverage_weight, 1.0),
        },
        "recompute_contract": {
            "formula": "sum(w_t * mean_charge_mt) / sum(w_t * mean_success_mt)",
            "zero_success_cells_retained": True,
            "missing_cells_not_imputed": True,
        },
        "evidence_audit": evidence_report,
        "underfilled_cells": underfilled_cells,
        "task_weights": task_weights,
        "cells": cells,
        "models": models,
    }


def build_workload_index(
    rows: Iterable[RolloutResult],
    *,
    prices: PriceCatalog | None = None,
    target_tasks_per_cell: int = 4,
) -> dict[str, object]:
    if target_tasks_per_cell <= 0:
        raise ValueError("target_tasks_per_cell must be positive")

    row_list = list(rows)
    task_weights = _task_weights(row_list, target_tasks_per_cell=target_tasks_per_cell)
    task_weight_by_key = {
        (str(task["category"]), str(task["size"]), str(task["task_id"])): task
        for task in task_weights
    }
    cell_summaries = aggregate_results(
        row_list,
        group_by=(
            "model_config",
            "model",
            "reasoning_effort",
            "category",
            "size",
            "task_id",
        ),
        prices=prices,
    )

    cells = []
    for summary in cell_summaries:
        weight = task_weight_by_key[
            (
                str(summary["category"]),
                str(summary["size"]),
                str(summary["task_id"]),
            )
        ]
        cells.append(
            {
                **summary,
                "default_weight": weight["default_weight"],
                "declared_weight": weight["declared_weight"],
            }
        )
    cells.sort(key=_cell_sort_key)

    models = _model_summaries(cells)
    coverage_weight = sum(float(task["declared_weight"]) for task in task_weights)

    return {
        "schema_version": WORKLOAD_INDEX_SCHEMA_VERSION,
        "weighting": {
            "scheme": "equal_category_equal_size_observed_task",
            "normalization": "renormalized_over_observed_tasks",
            "included_sizes": list(SIZE_ORDER),
            "categories": [
                {"category": category, "weight": 1 / len(CATEGORY_ORDER)}
                for category in CATEGORY_ORDER
            ],
            "sizes": [
                {"size": size, "weight_within_category": 1 / len(SIZE_ORDER)}
                for size in SIZE_ORDER
            ],
            "target_tasks_per_category_size": target_tasks_per_cell,
            "declared_coverage_weight": coverage_weight,
        },
        "recompute_contract": {
            "task_weight_formula": (
                "category_weight * size_weight_within_category * "
                "task_weight_within_category_size, normalized over selected tasks"
            ),
            "basket_metric_formula": (
                "weighted_mean_cost_per_attempt / weighted_pass_rate for CPSC; "
                "weighted_mean_tokens_per_attempt / weighted_pass_rate for tokens"
            ),
            "primary_metrics": ["cpsc", "tokens_per_success", "pass_rate"],
        },
        "task_weights": task_weights,
        "cells": cells,
        "models": models,
    }


def _task_weights(
    rows: list[RolloutResult],
    *,
    target_tasks_per_cell: int,
) -> list[dict[str, object]]:
    tasks = sorted(
        {(row.category, row.size, row.task_id) for row in rows},
        key=lambda item: (_category_rank(item[0]), _size_rank(item[1]), item[2]),
    )
    if not tasks:
        return []

    observed_by_cell: dict[tuple[str, str], int] = defaultdict(int)
    for category, size, _task_id in tasks:
        observed_by_cell[(category, size)] += 1

    raw_weights = []
    for category, size, task_id in tasks:
        category_weight = 1 / len(CATEGORY_ORDER)
        size_weight = 1 / len(SIZE_ORDER)
        observed_tasks_in_cell = observed_by_cell[(category, size)]
        raw_observed_weight = category_weight * size_weight / observed_tasks_in_cell
        declared_weight = category_weight * size_weight / target_tasks_per_cell
        raw_weights.append(
            {
                "task_id": task_id,
                "category": category,
                "size": size,
                "category_weight": category_weight,
                "size_weight_within_category": size_weight,
                "observed_tasks_in_category_size": observed_tasks_in_cell,
                "target_tasks_in_category_size": target_tasks_per_cell,
                "raw_observed_weight": raw_observed_weight,
                "declared_weight": declared_weight,
            }
        )

    total_raw_weight = sum(float(task["raw_observed_weight"]) for task in raw_weights)
    return [
        {
            **task,
            "default_weight": float(task["raw_observed_weight"]) / total_raw_weight,
        }
        for task in raw_weights
    ]


def _model_summaries(cells: list[dict[str, object]]) -> list[dict[str, object]]:
    cells_by_model: dict[str, list[dict[str, object]]] = defaultdict(list)
    for cell in cells:
        cells_by_model[str(cell["model_config"])].append(cell)

    summaries = []
    for model_config, model_cells in sorted(cells_by_model.items()):
        covered_weight = sum(float(cell["default_weight"]) for cell in model_cells)
        priced_success_weight = _metric_weight(model_cells, "cpsc")
        token_success_weight = _metric_weight(model_cells, "tokens_per_success")
        weighted_pass_rate = _weighted_metric(model_cells, "pass_rate")
        weighted_mean_cost = _weighted_metric(
            model_cells,
            "mean_cost_per_attempt",
            require_complete=True,
        )
        weighted_mean_tokens = _weighted_metric(
            model_cells,
            "mean_tokens_per_attempt",
            require_complete=True,
        )
        partial_weighted_mean_cost = _weighted_metric(model_cells, "mean_cost_per_attempt")
        partial_weighted_mean_tokens = _weighted_metric(model_cells, "mean_tokens_per_attempt")
        first_cell = model_cells[0]
        summary = {
            "model_config": model_config,
            "model": first_cell["model"],
            "reasoning_effort": first_cell.get("reasoning_effort"),
            "cells": len(model_cells),
            "covered_weight": covered_weight,
            "missing_weight": max(0.0, 1.0 - covered_weight),
            "priced_success_weight": priced_success_weight,
            "token_success_weight": token_success_weight,
            "unresolved_weight": max(0.0, covered_weight - priced_success_weight),
            "weighted_pass_rate": weighted_pass_rate,
            "weighted_mean_turns": _weighted_metric(model_cells, "mean_turns"),
            "weighted_mean_cost_per_attempt": weighted_mean_cost,
            "partial_weighted_mean_cost_per_attempt": partial_weighted_mean_cost,
            "weighted_mean_tokens_per_attempt": weighted_mean_tokens,
            "partial_weighted_mean_tokens_per_attempt": partial_weighted_mean_tokens,
            "basket_cpsc": _ratio_or_none(weighted_mean_cost, weighted_pass_rate),
            "partial_basket_cpsc": _ratio_or_none(partial_weighted_mean_cost, weighted_pass_rate),
            "basket_tokens_per_success": _ratio_or_none(weighted_mean_tokens, weighted_pass_rate),
            "partial_basket_tokens_per_success": _ratio_or_none(
                partial_weighted_mean_tokens,
                weighted_pass_rate,
            ),
        }
        summaries.append(summary)

    _rank_models(summaries, "basket_cpsc", "rank_by_basket_cpsc")
    _rank_models(
        summaries,
        "basket_tokens_per_success",
        "rank_by_basket_tokens_per_success",
    )
    return summaries


def _metric_weight(cells: list[dict[str, object]], metric: str) -> float:
    return sum(float(cell["default_weight"]) for cell in cells if _is_number(cell.get(metric)))


def _weighted_metric(
    cells: list[dict[str, object]],
    metric: str,
    *,
    require_complete: bool = False,
) -> float | None:
    weighted_total = 0.0
    metric_weight = 0.0
    for cell in cells:
        value = cell.get(metric)
        if not _is_number(value):
            continue
        weight = float(cell["default_weight"])
        weighted_total += weight * float(value)
        metric_weight += weight

    if metric_weight == 0:
        return None
    if require_complete and not _weights_match(metric_weight, 1.0):
        return None
    return weighted_total if require_complete else weighted_total / metric_weight


def _rank_models(
    summaries: list[dict[str, object]],
    metric: str,
    rank_field: str,
) -> None:
    ranked = [
        summary
        for summary in summaries
        if _is_number(summary.get(metric))
    ]
    ranked.sort(key=lambda summary: (float(summary[metric]), str(summary["model"])))
    for rank, summary in enumerate(ranked, start=1):
        summary[rank_field] = rank
    for summary in summaries:
        summary.setdefault(rank_field, None)


def _cell_sort_key(cell: dict[str, object]) -> tuple[object, ...]:
    return (
        str(cell["model_config"]),
        _category_rank(str(cell["category"])),
        _size_rank(str(cell["size"])),
        str(cell["task_id"]),
    )


def _category_rank(category: str) -> int:
    return CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else len(CATEGORY_ORDER)


def _size_rank(size: str) -> int:
    return SIZE_ORDER.index(size) if size in SIZE_ORDER else len(SIZE_ORDER)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _weights_match(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-9


def _ratio_or_none(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _complete_mean(values: list[float | None]) -> float | None:
    if not values or any(value is None for value in values):
        return None
    return sum(float(value) for value in values if value is not None) / len(values)


def _declared_weighted_sum(
    cells: list[dict[str, object]],
    metric: str,
) -> float | None:
    if any(not _is_number(cell.get(metric)) for cell in cells):
        return None
    return sum(float(cell["declared_weight"]) * float(cell[metric]) for cell in cells)

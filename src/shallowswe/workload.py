from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .results import PriceCatalog, RolloutResult, aggregate_results
from .task_metadata import CATEGORY_ORDER, SIZE_ORDER


WORKLOAD_INDEX_SCHEMA_VERSION = "shallowswe.workload_index.v0.3"


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

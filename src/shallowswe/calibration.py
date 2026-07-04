from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Iterable

from .results import RolloutResult
from .task_metadata import SIZE_ORDER


FLOOR_SELECTION_SCHEMA_VERSION = "shallowswe.floor_selection.v0.1"
ONE_SHOT_CEILING_GATE_SCHEMA_VERSION = "shallowswe.one_shot_ceiling_gate.v0.1"


def select_floor_pair(
    rows: Iterable[RolloutResult],
    *,
    saturation_threshold: float = 0.85,
) -> dict[str, object]:
    if not 0 < saturation_threshold <= 1:
        raise ValueError("saturation_threshold must be in (0, 1]")

    scored_rows = [row for row in rows if row.is_scored]
    by_model: dict[str, list[RolloutResult]] = defaultdict(list)
    for row in scored_rows:
        by_model[row.model_config].append(row)

    candidates = [
        _candidate_summary(model_config, model_rows, saturation_threshold)
        for model_config, model_rows in sorted(by_model.items())
    ]
    candidates.sort(
        key=lambda candidate: (
            not bool(candidate["floor_candidate"]),
            -float(candidate["task_pass_rate_range"]),
            -int(candidate["large_band_task_count"]),
            float(candidate["overall_pass_rate"]),
            str(candidate["model_config"]),
        )
    )

    recommended = next(
        (
            str(candidate["model_config"])
            for candidate in candidates
            if candidate["floor_candidate"]
        ),
        None,
    )

    return {
        "schema_version": FLOOR_SELECTION_SCHEMA_VERSION,
        "saturation_threshold": saturation_threshold,
        "recommended_floor_model_config": recommended,
        "selection_rule": (
            "choose the non-saturated pair with the widest task pass-rate spread; "
            "large-band count breaks ties"
        ),
        "candidates": candidates,
    }


def evaluate_one_shot_ceiling_gate(
    rows: Iterable[RolloutResult],
    *,
    pass_threshold: float = 0.75,
    target_rollouts: int = 16,
) -> dict[str, object]:
    if not 0 < pass_threshold <= 1:
        raise ValueError("pass_threshold must be in (0, 1]")
    if target_rollouts < 1:
        raise ValueError("target_rollouts must be positive")

    accept_min_passes = ceil(target_rollouts * pass_threshold)
    investigate_min_passes = max(0, accept_min_passes - 1)
    scored_rows = [row for row in rows if row.is_scored]

    by_model_task: dict[tuple[str, str], list[RolloutResult]] = defaultdict(list)
    for row in scored_rows:
        by_model_task[(row.model_config, row.task_id)].append(row)

    cells = [
        _ceiling_gate_cell(
            model_config=model_config,
            task_id=task_id,
            rows=task_rows,
            pass_threshold=pass_threshold,
            target_rollouts=target_rollouts,
            accept_min_passes=accept_min_passes,
            investigate_min_passes=investigate_min_passes,
        )
        for (model_config, task_id), task_rows in sorted(by_model_task.items())
    ]

    return {
        "schema_version": ONE_SHOT_CEILING_GATE_SCHEMA_VERSION,
        "pass_threshold": pass_threshold,
        "target_rollouts": target_rollouts,
        "accept_min_passes": accept_min_passes,
        "investigate_min_passes": investigate_min_passes,
        "model_summaries": _ceiling_model_summaries(cells),
        "tasks": cells,
    }


def _candidate_summary(
    model_config: str,
    rows: list[RolloutResult],
    saturation_threshold: float,
) -> dict[str, object]:
    task_rates = _rates_by(rows, ("task_id",))
    size_rates = _rates_by(rows, ("size",))
    cell_rates = _rates_by(rows, ("category", "size"))
    overall_pass_rate = _pass_rate(rows)
    task_pass_rates = list(task_rates.values())
    large_task_rates = [
        rate
        for key, rate in task_rates.items()
        if _task_size(rows, str(key[0])) == "large"
    ]
    task_range = (
        max(task_pass_rates) - min(task_pass_rates)
        if task_pass_rates
        else 0.0
    )

    return {
        "model_config": model_config,
        "attempts": len(rows),
        "tasks": len(task_rates),
        "overall_pass_rate": overall_pass_rate,
        "saturated_overall": overall_pass_rate > saturation_threshold,
        "floor_candidate": overall_pass_rate <= saturation_threshold,
        "task_pass_rate_min": min(task_pass_rates) if task_pass_rates else None,
        "task_pass_rate_max": max(task_pass_rates) if task_pass_rates else None,
        "task_pass_rate_range": task_range,
        "large_band_task_count": sum(1 for rate in large_task_rates if 0.0 <= rate <= 0.4),
        "size_pass_rates": {
            size: size_rates.get((size,))
            for size in SIZE_ORDER
        },
        "category_size_pass_rates": {
            f"{category}/{size}": rate
            for (category, size), rate in sorted(cell_rates.items())
        },
    }


def _ceiling_gate_cell(
    *,
    model_config: str,
    task_id: str,
    rows: list[RolloutResult],
    pass_threshold: float,
    target_rollouts: int,
    accept_min_passes: int,
    investigate_min_passes: int,
) -> dict[str, object]:
    attempts = len(rows)
    passes = sum(1 for row in rows if row.passed)
    pass_rate = passes / attempts if attempts else 0.0
    decision = _ceiling_gate_decision(
        attempts=attempts,
        passes=passes,
        target_rollouts=target_rollouts,
        accept_min_passes=accept_min_passes,
        investigate_min_passes=investigate_min_passes,
    )
    return {
        "model_config": model_config,
        "task_id": task_id,
        "category": rows[0].category if rows else None,
        "size": rows[0].size if rows else None,
        "attempts": attempts,
        "passes": passes,
        "pass_rate": pass_rate,
        "pass_threshold": pass_threshold,
        "target_rollouts": target_rollouts,
        "missing_rollouts": max(0, target_rollouts - attempts),
        "decision": decision,
    }


def _ceiling_gate_decision(
    *,
    attempts: int,
    passes: int,
    target_rollouts: int,
    accept_min_passes: int,
    investigate_min_passes: int,
) -> str:
    if attempts < target_rollouts:
        return "needs_more_rollouts"
    if passes >= accept_min_passes:
        return "accept"
    if passes >= investigate_min_passes:
        return "investigate"
    return "fix_or_evict"


def _ceiling_model_summaries(cells: list[dict[str, object]]) -> list[dict[str, object]]:
    by_model: dict[str, list[dict[str, object]]] = defaultdict(list)
    for cell in cells:
        by_model[str(cell["model_config"])].append(cell)

    summaries: list[dict[str, object]] = []
    for model_config, model_cells in sorted(by_model.items()):
        decision_counts: dict[str, int] = defaultdict(int)
        for cell in model_cells:
            decision_counts[str(cell["decision"])] += 1
        attempts = sum(int(cell["attempts"]) for cell in model_cells)
        passes = sum(int(cell["passes"]) for cell in model_cells)
        clears_gate = bool(model_cells) and all(
            cell["decision"] == "accept" for cell in model_cells
        )
        summaries.append(
            {
                "model_config": model_config,
                "tasks": len(model_cells),
                "attempts": attempts,
                "passes": passes,
                "diagnostic_pass_rate": passes / attempts if attempts else 0.0,
                "decision_counts": dict(sorted(decision_counts.items())),
                "clears_gate": clears_gate,
            }
        )
    return summaries


def _rates_by(
    rows: list[RolloutResult],
    fields: tuple[str, ...],
) -> dict[tuple[str, ...], float]:
    groups: dict[tuple[str, ...], list[RolloutResult]] = defaultdict(list)
    for row in rows:
        groups[tuple(str(getattr(row, field)) for field in fields)].append(row)
    return {
        key: _pass_rate(group)
        for key, group in groups.items()
    }


def _pass_rate(rows: list[RolloutResult]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.passed) / len(rows)


def _task_size(rows: list[RolloutResult], task_id: str) -> str | None:
    for row in rows:
        if row.task_id == task_id:
            return row.size
    return None

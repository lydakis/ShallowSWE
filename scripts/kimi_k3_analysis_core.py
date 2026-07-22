"""Shared deterministic helpers for the existing-data Kimi K3 article analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import itertools
import math
from statistics import median
from typing import Any


Row = Mapping[str, Any]


def mean(values: Sequence[float]) -> float:
    if not values:
        return math.nan
    return sum(values) / len(values)


def pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return math.nan
    left_mean = mean(left)
    right_mean = mean(right)
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    if left_ss <= 0 or right_ss <= 0:
        return math.nan
    cross = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    return cross / math.sqrt(left_ss * right_ss)


def rankdata(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        average_rank = (position + 1 + end) / 2
        for ordered_index in order[position:end]:
            ranks[ordered_index] = average_rank
        position = end
    return ranks


def residualize(values: Sequence[float], control: Sequence[float]) -> list[float]:
    if len(values) != len(control) or not values:
        raise ValueError("values and control must have the same non-zero length")
    control_mean = mean(control)
    value_mean = mean(values)
    denominator = sum((value - control_mean) ** 2 for value in control)
    if denominator <= 0:
        return [value - value_mean for value in values]
    slope = (
        sum(
            (control_value - control_mean) * (value - value_mean)
            for value, control_value in zip(values, control, strict=True)
        )
        / denominator
    )
    intercept = value_mean - slope * control_mean
    return [
        value - (intercept + slope * control_value)
        for value, control_value in zip(values, control, strict=True)
    ]


def empirical_logit(rate: float, *, attempts: int = 4, pseudocount: float = 0.5) -> float:
    successes = rate * attempts
    return math.log((successes + pseudocount) / (attempts - successes + pseudocount))


def lineage_correlations(
    k3: Sequence[float],
    k2: Sequence[float],
    fable: Sequence[float],
    *,
    control: Sequence[float] | None,
    transform: str,
    attempts: int = 4,
    pseudocount: float = 0.5,
) -> dict[str, float]:
    series = [list(k3), list(k2), list(fable)]
    control_values = list(control) if control is not None else None
    if transform == "rank":
        series = [rankdata(values) for values in series]
        if control_values is not None:
            control_values = rankdata(control_values)
    elif transform == "empirical_logit":
        series = [
            [empirical_logit(value, attempts=attempts, pseudocount=pseudocount) for value in values]
            for values in series
        ]
        if control_values is not None:
            control_values = [
                empirical_logit(value, attempts=attempts, pseudocount=pseudocount)
                for value in control_values
            ]
    elif transform != "raw":
        raise ValueError(f"unknown lineage transform: {transform}")

    if control_values is not None:
        series = [residualize(values, control_values) for values in series]
    k3_values, k2_values, fable_values = series
    k3_k2 = pearson(k3_values, k2_values)
    k3_fable = pearson(k3_values, fable_values)
    return {
        "k3_k2_correlation": k3_k2,
        "k3_fable_correlation": k3_fable,
        "fable_minus_k2_difference": k3_fable - k3_k2,
    }


def percentile(values: Sequence[float], probability: float) -> float:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return math.nan
    if len(clean) == 1:
        return clean[0]
    position = probability * (len(clean) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[lower]
    weight = position - lower
    return clean[lower] * (1 - weight) + clean[upper] * weight


def interval(values: Sequence[float]) -> list[float]:
    return [percentile(values, 0.025), percentile(values, 0.975)]


def reported_cost(row: Row) -> float:
    value = row.get("_analysis_cost_usd", row.get("cost_usd"))
    if value is None:
        raise ValueError(f"trial {row.get('trial_name')} has no analysis cost")
    return float(value)


def reprice_k3(
    row: Row,
    cache_fraction: float,
    prices: Mapping[str, float],
) -> float:
    input_tokens = int(row.get("n_input_tokens") or 0)
    output_tokens = int(row.get("n_output_tokens") or 0)
    input_rate = (
        float(prices["uncached_input"]) * (1 - cache_fraction)
        + float(prices["cached_input"]) * cache_fraction
    )
    return (input_tokens * input_rate + output_tokens * float(prices["output"])) / 1_000_000


def summarize_retry_task(rows: Sequence[Row], *, attempts: int) -> dict[str, float]:
    ordered_rows = sorted(rows, key=lambda row: str(row.get("trial_name", "")))
    if attempts < 1 or attempts > len(ordered_rows):
        raise ValueError("attempt count must fit the available rows")
    sequences = itertools.permutations(ordered_rows, attempts)
    sequence_count = 0
    coverage = 0.0
    stopped_cost = 0.0
    for sequence in sequences:
        sequence_count += 1
        for row in sequence:
            stopped_cost += reported_cost(row)
            if bool(row.get("passed")):
                coverage += 1
                break
    return {
        "coverage": coverage / sequence_count,
        "stopped_cost_usd": stopped_cost / sequence_count,
    }


def spend_decomposition(rows: Sequence[Row]) -> dict[str, float | int]:
    successes = [row for row in rows if bool(row.get("passed"))]
    failures = [row for row in rows if not bool(row.get("passed"))]
    if not successes:
        raise ValueError("spend decomposition requires at least one success")
    pass_rate = len(successes) / len(rows)
    success_mean = mean([reported_cost(row) for row in successes])
    failure_mean = mean([reported_cost(row) for row in failures]) if failures else 0.0
    reliability_tax = ((1 - pass_rate) / pass_rate) * failure_mean
    return {
        "attempts": len(rows),
        "successes": len(successes),
        "failures": len(failures),
        "pass_rate": pass_rate,
        "mean_success_cost_usd": success_mean,
        "mean_failure_cost_usd": failure_mean,
        "realized_reliability_tax_usd": reliability_tax,
        "realized_cpsc_usd": success_mean + reliability_tax,
    }


def summarize_cache_rows(
    rows: Sequence[Row],
    bins: Sequence[tuple[int, int | None]],
) -> dict[str, Any]:
    shares = [
        float(row["cache_read_tokens"]) / float(row["input_tokens"])
        for row in rows
        if int(row["input_tokens"]) > 0
    ]
    total_input = sum(int(row["input_tokens"]) for row in rows)
    total_cache = sum(int(row["cache_read_tokens"]) for row in rows)
    step_values = [float(row["agent_steps"]) for row in rows]
    bin_rows = []
    for lower, upper in bins:
        selected = [
            row
            for row in rows
            if int(row["agent_steps"]) >= lower
            and (upper is None or int(row["agent_steps"]) <= upper)
        ]
        selected_input = sum(int(row["input_tokens"]) for row in selected)
        selected_cache = sum(int(row["cache_read_tokens"]) for row in selected)
        bin_rows.append(
            {
                "label": f"{lower}+" if upper is None else f"{lower}-{upper}",
                "lower_steps": lower,
                "upper_steps": upper,
                "attempts": len(selected),
                "input_tokens": selected_input,
                "cache_read_tokens": selected_cache,
                "token_weighted_cache_share": (
                    selected_cache / selected_input if selected_input else math.nan
                ),
                "median_attempt_cache_share": (
                    median(
                        float(row["cache_read_tokens"]) / float(row["input_tokens"])
                        for row in selected
                    )
                    if selected
                    else math.nan
                ),
            }
        )
    return {
        "attempts": len(rows),
        "tasks": len({str(row["task_id"]) for row in rows}),
        "input_tokens": total_input,
        "cache_read_tokens": total_cache,
        "token_weighted_cache_share": total_cache / total_input,
        "median_attempt_cache_share": median(shares),
        "steps_cache_share_correlation": pearson(step_values, shares),
        "log_steps_cache_share_correlation": pearson(
            [math.log(value) for value in step_values], shares
        ),
        "step_bins": bin_rows,
    }

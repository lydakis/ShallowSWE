from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from math import log, sqrt
from pathlib import Path
from random import Random
from statistics import NormalDist, mean, median
from typing import Any


DEEPSWE_ECONOMICS_SCHEMA_VERSION = "shallowswe.deepswe_economics.v0.1"
MISSING_COST_METHODS = {
    "config_mean",
    "config_outcome_median",
    "complete_case",
    "zero",
}
DEFAULT_RELIABILITY_FLOORS = tuple(index / 20 for index in range(16))
MISSING_COST_PLAN_NAMES = {
    "within_configuration_mean_imputation": "config_mean",
    "zero_cost_lower_bound": "zero",
    "within_configuration_outcome_median_imputation": "config_outcome_median",
    "cost_complete_rows_only": "complete_case",
}
RESOURCE_FIELD_SPECS = (
    ("agent_steps_per_success", "n_agent_steps"),
    ("input_tokens_per_success", "n_input_tokens"),
    ("cache_tokens_per_success", "n_cache_tokens"),
    ("output_tokens_per_success", "n_output_tokens"),
    ("agent_seconds_per_success", "agent_duration_seconds"),
    ("trial_seconds_per_success", "trial_duration_seconds"),
)
RESOURCE_METRICS = tuple(field for field, _ in RESOURCE_FIELD_SPECS) + (
    "total_tokens_per_success",
)


def verify_artifact(
    path: Path,
    *,
    expected_bytes: int,
    expected_sha256: str,
) -> dict[str, object]:
    payload = path.read_bytes()
    actual_bytes = len(payload)
    actual_sha256 = sha256(payload).hexdigest()
    issues = []
    if actual_bytes != expected_bytes:
        issues.append(f"bytes:{actual_bytes}!={expected_bytes}")
    if actual_sha256 != expected_sha256:
        issues.append(f"sha256:{actual_sha256}!={expected_sha256}")
    if issues:
        raise ValueError(f"artifact verification failed for {path}: {', '.join(issues)}")
    return {
        "path": str(path),
        "bytes": actual_bytes,
        "sha256": actual_sha256,
        "verified": True,
    }


def analyze_deepswe_trials(
    payload: dict[str, Any],
    *,
    missing_cost_method: str = "config_mean",
) -> dict[str, object]:
    if missing_cost_method not in MISSING_COST_METHODS:
        raise ValueError(f"unknown missing-cost method: {missing_cost_method}")
    source_rows = payload.get("rows")
    if not isinstance(source_rows, list):
        raise ValueError("DeepSWE trial artifact missing rows list")

    scored_rows = [row for row in source_rows if _is_scored_deepswe_row(row)]
    missing_rows = [row for row in scored_rows if row.get("cost_usd") is None]
    analysis_rows = _prepare_analysis_rows(scored_rows, missing_cost_method)
    configurations = _summarize_configurations(analysis_rows)
    _attach_ranks(configurations)
    _attach_attempt_cost_frontier(configurations)
    display_configurations = _select_display_configurations(configurations)
    _attach_ranks(display_configurations)
    _attach_attempt_cost_frontier(display_configurations)
    task_mix = _analyze_task_mix(analysis_rows)
    task_weighting_sensitivity = _analyze_task_weighting_sensitivity(
        analysis_rows,
        pooled_configurations=configurations,
    )
    resource_intensity = _analyze_resource_intensity(
        analysis_rows,
        pooled_configurations=configurations,
    )

    return {
        "schema_version": DEEPSWE_ECONOMICS_SCHEMA_VERSION,
        "missing_cost_method": missing_cost_method,
        "cohort": {
            "source_rows": len(source_rows),
            "scored_rows": len(scored_rows),
            "excluded_rows": len(source_rows) - len(scored_rows),
            "analysis_rows": len(analysis_rows),
        },
        "missing_cost": {
            "scored_missing_rows": len(missing_rows),
            "affected_configurations": sorted(
                {str(row.get("config")) for row in missing_rows}
            ),
        },
        "configurations": configurations,
        "display_configurations": display_configurations,
        "rank_association": _rank_association(configurations),
        "display_rank_association": _rank_association(display_configurations),
        "effort_rank_association": _effort_rank_association(configurations),
        "reliability_floor_curve": _reliability_floor_curve(configurations),
        "display_reliability_floor_curve": _reliability_floor_curve(
            display_configurations
        ),
        "task_weighting_sensitivity": task_weighting_sensitivity,
        "resource_intensity": resource_intensity,
        "task_mix": task_mix,
        "infrastructure_exclusion_audit": _audit_infrastructure_exclusions(
            source_rows,
            analysis_rows,
        ),
    }


def derive_deepswe_trial_rows(
    payload: dict[str, Any],
    *,
    missing_cost_method: str = "config_mean",
) -> list[dict[str, object]]:
    """Return the scored trial cohort with explicit analysis-cost provenance."""
    if missing_cost_method not in MISSING_COST_METHODS:
        raise ValueError(f"unknown missing-cost method: {missing_cost_method}")
    source_rows = payload.get("rows")
    if not isinstance(source_rows, list):
        raise ValueError("DeepSWE trial artifact missing rows list")
    scored_rows = [row for row in source_rows if _is_scored_deepswe_row(row)]
    prepared = _prepare_analysis_rows(scored_rows, missing_cost_method)
    fields = (
        "trial_name",
        "task_name",
        "config",
        "model",
        "provider",
        "harness",
        "reasoning_effort",
        "passed",
        "outcome",
        "n_input_tokens",
        "n_cache_tokens",
        "n_output_tokens",
        "n_agent_steps",
        "agent_duration_seconds",
        "trial_duration_seconds",
    )
    derived = []
    for row in prepared:
        result = {field: row.get(field) for field in fields}
        result.update(
            {
                "reported_cost_usd": row.get("cost_usd"),
                "analysis_cost_usd": row["_analysis_cost_usd"],
                "cost_imputed": row["_cost_imputed"],
                "missing_cost_method": missing_cost_method,
            }
        )
        derived.append(result)
    return derived


def bootstrap_deepswe_trials(
    payload: dict[str, Any],
    *,
    replicates: int,
    seed: int,
    missing_cost_method: str = "config_mean",
) -> dict[str, object]:
    if replicates <= 0:
        raise ValueError("bootstrap replicates must be positive")
    source_rows = payload.get("rows")
    if not isinstance(source_rows, list):
        raise ValueError("DeepSWE trial artifact missing rows list")
    scored_rows = [row for row in source_rows if _is_scored_deepswe_row(row)]
    analysis_rows = _prepare_analysis_rows(scored_rows, missing_cost_method)
    tasks = sorted({_required_str(row, "task_name") for row in analysis_rows})
    configs = sorted({_required_str(row, "config") for row in analysis_rows})
    matrix = _task_stat_matrix(analysis_rows, configs=configs, tasks=tasks)
    resource_matrix = _task_resource_matrix(
        analysis_rows,
        configs=configs,
        tasks=tasks,
    )
    point_configurations = _summarize_configurations(analysis_rows)
    _attach_ranks(point_configurations)
    point_display = _select_display_configurations(point_configurations)
    fixed_display_configs = {str(row["config"]) for row in point_display}
    point_floor_curve = {
        float(row["minimum_pass_rate"]): row
        for row in _reliability_floor_curve(point_configurations)
    }
    model_by_config = {
        str(row["config"]): str(row.get("model") or row["config"])
        for row in point_configurations
    }
    model_counts = Counter(model_by_config.values())
    repeated_models = sorted(model for model, count in model_counts.items() if count >= 2)
    samples: dict[str, dict[str, list[float | None]]] = {
        config: {
            "pass_rate": [],
            "realized_cpsc_usd": [],
            "conditional_successful_spend_usd": [],
            "conditional_failed_spend_usd": [],
            "realized_reliability_tax_usd": [],
            "realized_reliability_tax_share": [],
            "pass_rate_rank": [],
            "realized_cpsc_rank": [],
            "rank_displacement": [],
        }
        for config in configs
    }
    association_samples: dict[str, dict[str, list[float | None]]] = {
        panel: {"spearman": [], "kendall_tau_b": []}
        for panel in (
            "all_configurations",
            "fixed_display_panel",
            "pooled_within_model",
        )
    }
    by_model_association_samples = {
        model: {"spearman": [], "kendall_tau_b": []}
        for model in repeated_models
    }
    floor_winners: dict[float, list[str | None]] = {
        floor: [] for floor in DEFAULT_RELIABILITY_FLOORS
    }
    floor_selected_cpsc: dict[float, list[float | None]] = {
        floor: [] for floor in DEFAULT_RELIABILITY_FLOORS
    }
    floor_selected_pass_rate: dict[float, list[float | None]] = {
        floor: [] for floor in DEFAULT_RELIABILITY_FLOORS
    }
    resource_complete = {
        config: {
            output_field: all(row.get(source_field) is not None for row in analysis_rows
                              if _required_str(row, "config") == config)
            for output_field, source_field in RESOURCE_FIELD_SPECS
        }
        for config in configs
    }
    for config in configs:
        resource_complete[config]["total_tokens_per_success"] = all(
            resource_complete[config][field]
            for field in (
                "input_tokens_per_success",
                "cache_tokens_per_success",
                "output_tokens_per_success",
            )
        )
    resource_samples: dict[str, dict[str, list[float | None]]] = {
        config: {
            field: [] for field in RESOURCE_METRICS
        }
        for config in configs
    }
    random = Random(seed)
    for _ in range(replicates):
        task_counts = [0] * len(tasks)
        for _ in tasks:
            task_counts[random.randrange(len(tasks))] += 1
        replicate_rows = []
        for config in configs:
            metrics = _bootstrap_metrics(matrix[config], task_counts)
            resource_metrics = _bootstrap_resource_metrics(
                resource_matrix[config], task_counts
            )
            for field, complete in resource_complete[config].items():
                if not complete:
                    resource_metrics[field] = None
            for field, value in metrics.items():
                samples[config][field].append(value)
            for field, value in resource_metrics.items():
                resource_samples[config][field].append(value)
            replicate_rows.append(
                {
                    "config": config,
                    "model": model_by_config[config],
                    "pass_rate": metrics["pass_rate"],
                    "realized_cpsc_usd": metrics["realized_cpsc_usd"],
                }
            )

        _attach_ranks(replicate_rows)
        for row in replicate_rows:
            config = str(row["config"])
            for field in (
                "pass_rate_rank",
                "realized_cpsc_rank",
                "rank_displacement",
            ):
                value = row.get(field)
                samples[config][field].append(float(value) if value is not None else None)

        _append_association_sample(
            association_samples["all_configurations"],
            _rank_association(replicate_rows),
        )
        display_rows = [
            dict(row)
            for row in replicate_rows
            if str(row["config"]) in fixed_display_configs
        ]
        _attach_ranks(display_rows)
        _append_association_sample(
            association_samples["fixed_display_panel"],
            _rank_association(display_rows),
        )
        effort_association = _effort_rank_association(replicate_rows)
        _append_association_sample(
            association_samples["pooled_within_model"],
            effort_association["pooled_within_model"],
        )
        for row in effort_association["by_model"]:
            model = str(row["model"])
            _append_association_sample(by_model_association_samples[model], row)

        for row in _reliability_floor_curve(replicate_rows):
            floor = float(row["minimum_pass_rate"])
            winner = row.get("minimum_cpsc_config")
            floor_winners[floor].append(str(winner) if winner is not None else None)
            selected_cpsc = row.get("minimum_cpsc_usd")
            selected_pass_rate = row.get("observed_pass_rate")
            floor_selected_cpsc[floor].append(
                float(selected_cpsc) if selected_cpsc is not None else None
            )
            floor_selected_pass_rate[floor].append(
                float(selected_pass_rate) if selected_pass_rate is not None else None
            )

    configuration_intervals = []
    for config in configs:
        config_samples = samples[config]
        row: dict[str, object] = {
            "config": config,
            "defined_cpsc_replicates": sum(
                value is not None for value in config_samples["realized_cpsc_usd"]
            ),
            "defined_cpsc_rank_replicates": sum(
                value is not None for value in config_samples["realized_cpsc_rank"]
            ),
        }
        for field, values in config_samples.items():
            low, high = _interval(values)
            row[f"{field}_ci_low"] = low
            row[f"{field}_ci_high"] = high
        configuration_intervals.append(row)

    interval_by_config = {
        str(row["config"]): row for row in configuration_intervals
    }
    lcb_floor_curve = []
    for floor in DEFAULT_RELIABILITY_FLOORS:
        eligible = [
            row
            for row in point_configurations
            if interval_by_config[str(row["config"])].get("pass_rate_ci_low")
            is not None
            and float(
                interval_by_config[str(row["config"])]["pass_rate_ci_low"]
            )
            >= floor
            and row.get("realized_cpsc_usd") is not None
        ]
        best = min(
            eligible,
            key=lambda row: (float(row["realized_cpsc_usd"]), str(row["config"])),
            default=None,
        )
        best_interval = interval_by_config.get(str(best["config"])) if best else None
        lcb_floor_curve.append(
            {
                "minimum_pass_rate": floor,
                "eligible_configurations": len(eligible),
                "minimum_cpsc_config": best.get("config") if best else None,
                "point_cpsc_usd": best.get("realized_cpsc_usd") if best else None,
                "point_pass_rate": best.get("pass_rate") if best else None,
                "pass_rate_ci_low": (
                    best_interval.get("pass_rate_ci_low") if best_interval else None
                ),
                "status": "exploratory_lower_95_percentile_bound_eligibility",
            }
        )

    reliability_floor_policy = []
    reliability_floor_selection_frequencies = []
    for floor in DEFAULT_RELIABILITY_FLOORS:
        winners = floor_winners[floor]
        counts = Counter(winner for winner in winners if winner is not None)
        defined = sum(counts.values())
        point_winner_value = point_floor_curve[floor].get("minimum_cpsc_config")
        point_winner = str(point_winner_value) if point_winner_value is not None else None
        point_winner_pass_samples = (
            samples[point_winner]["pass_rate"] if point_winner is not None else []
        )
        point_winner_defined = sum(
            value is not None for value in point_winner_pass_samples
        )
        point_winner_meets = sum(
            value is not None and float(value) >= floor
            for value in point_winner_pass_samples
        )
        selected_cpsc_low, selected_cpsc_high = _interval(
            floor_selected_cpsc[floor]
        )
        selected_pass_low, selected_pass_high = _interval(
            floor_selected_pass_rate[floor]
        )
        most_selected = min(
            counts,
            key=lambda config: (-counts[config], config),
            default=None,
        )
        reliability_floor_policy.append(
            {
                "minimum_pass_rate": floor,
                "point_estimate_winner": point_winner,
                "point_winner_selection_count": counts.get(point_winner, 0),
                "point_winner_selection_share_all_replicates": (
                    counts.get(point_winner, 0) / replicates
                    if point_winner is not None
                    else None
                ),
                "selection_defined_replicates": defined,
                "no_eligible_configuration_replicates": replicates - defined,
                "most_selected_config": most_selected,
                "most_selected_count": counts.get(most_selected, 0),
                "most_selected_share_all_replicates": (
                    counts.get(most_selected, 0) / replicates if most_selected else None
                ),
                "selected_cpsc_usd_ci_low": selected_cpsc_low,
                "selected_cpsc_usd_ci_high": selected_cpsc_high,
                "selected_pass_rate_ci_low": selected_pass_low,
                "selected_pass_rate_ci_high": selected_pass_high,
                "point_winner_pass_rate_defined_replicates": point_winner_defined,
                "point_winner_meets_floor_replicates": point_winner_meets,
                "point_winner_meets_floor_bootstrap_share": (
                    point_winner_meets / point_winner_defined
                    if point_winner_defined
                    else None
                ),
            }
        )
        for config, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        ):
            reliability_floor_selection_frequencies.append(
                {
                    "minimum_pass_rate": floor,
                    "config": config,
                    "selection_count": count,
                    "selection_share_all_replicates": count / replicates,
                    "selection_share_when_defined": count / defined if defined else None,
                }
            )

    point_cpsc = {
        str(row["config"]): (
            float(row["realized_cpsc_usd"])
            if row.get("realized_cpsc_usd") is not None
            else None
        )
        for row in point_configurations
    }
    jackknife_cpsc = _delete_one_task_cpsc(matrix, configs)
    task_weighting_sensitivity = _bootstrap_equal_task_weighting_sensitivity(
        matrix,
        configs=configs,
        tasks=tasks,
        point_configurations=point_configurations,
        analysis_rows=analysis_rows,
        replicates=replicates,
        seed=seed,
    )
    point_resources = _analyze_resource_intensity(
        analysis_rows,
        pooled_configurations=point_configurations,
    )
    resource_intervals = []
    for config in configs:
        interval_row: dict[str, object] = {"config": config}
        for field, values in resource_samples[config].items():
            low, high = _interval(values)
            interval_row[f"{field}_ci_low"] = low
            interval_row[f"{field}_ci_high"] = high
            interval_row[f"{field}_defined_replicates"] = sum(
                value is not None for value in values
            )
        resource_intervals.append(interval_row)

    return {
        "schema_version": DEEPSWE_ECONOMICS_SCHEMA_VERSION,
        "method": "task_cluster_bootstrap",
        "cluster_count": len(tasks),
        "replicates": replicates,
        "seed": seed,
        "missing_cost_method": missing_cost_method,
        "fixed_display_configurations": sorted(fixed_display_configs),
        "configurations": configuration_intervals,
        "paired_comparisons": _paired_cpsc_comparisons(
            configs,
            samples,
            point_cpsc=point_cpsc,
            jackknife_cpsc=jackknife_cpsc,
        ),
        "rank_association_intervals": {
            panel: _association_interval(values)
            for panel, values in association_samples.items()
        },
        "within_model_rank_association_intervals": [
            {
                "model": model,
                **_association_interval(by_model_association_samples[model]),
            }
            for model in repeated_models
        ],
        "reliability_floor_policy": reliability_floor_policy,
        "reliability_floor_lcb_eligibility": lcb_floor_curve,
        "reliability_floor_selection_frequencies": (
            reliability_floor_selection_frequencies
        ),
        "task_weighting_sensitivity": task_weighting_sensitivity,
        "resource_intensity": resource_intervals,
        "paired_resource_comparisons": _paired_resource_comparisons(
            configs,
            resource_samples,
            point_resources=point_resources,
        ),
    }


def analyze_failure_charge_sensitivity(
    payload: dict[str, Any],
    *,
    anchor_config: str,
    multipliers: tuple[float, ...],
    missing_cost_method: str = "config_mean",
) -> dict[str, object]:
    if not multipliers or any(multiplier < 0 for multiplier in multipliers):
        raise ValueError("failure-charge multipliers must be non-negative")
    source_rows = payload.get("rows")
    if not isinstance(source_rows, list):
        raise ValueError("DeepSWE trial artifact missing rows list")
    scored_rows = [row for row in source_rows if _is_scored_deepswe_row(row)]
    analysis_rows = _prepare_analysis_rows(scored_rows, missing_cost_method)
    task_names = sorted({_required_str(row, "task_name") for row in analysis_rows})
    anchor_costs: dict[str, list[float]] = defaultdict(list)
    for row in scored_rows:
        if row.get("config") != anchor_config or row.get("cost_usd") is None:
            continue
        anchor_costs[_required_str(row, "task_name")].append(float(row["cost_usd"]))
    missing_anchor_tasks = [task for task in task_names if not anchor_costs[task]]
    if missing_anchor_tasks:
        raise ValueError(
            f"anchor configuration lacks cost-complete rows for {len(missing_anchor_tasks)} tasks"
        )
    base_budgets = {task: median(anchor_costs[task]) for task in task_names}

    scenarios = []
    for multiplier in multipliers:
        configurations = _summarize_failure_charge_scenario(
            analysis_rows,
            base_budgets=base_budgets,
            multiplier=float(multiplier),
        )
        ranks = _average_ranks(
            configurations, "proxy_failure_charge_cpsc_usd", reverse=False
        )
        for row in configurations:
            row["proxy_failure_charge_cpsc_rank"] = ranks.get(str(row["config"]))
        scenarios.append(
            {
                "multiplier": float(multiplier),
                "configurations": configurations,
            }
        )
    return {
        "schema_version": DEEPSWE_ECONOMICS_SCHEMA_VERSION,
        "status": "retrospective_sensitivity_not_calibration",
        "proxy_budget_construction": "median_anchor_observed_spend_by_task",
        "anchor_config": anchor_config,
        "anchor_task_coverage": len(base_budgets),
        "base_budget_summary_usd": {
            "minimum": min(base_budgets.values()),
            "median": median(base_budgets.values()),
            "maximum": max(base_budgets.values()),
        },
        "scenarios": scenarios,
    }


def analyze_anchor_success_budget_sensitivity(
    payload: dict[str, Any],
    *,
    anchor_config: str,
    multipliers: tuple[float, ...],
    missing_cost_method: str = "config_mean",
) -> dict[str, object]:
    if not multipliers or any(multiplier < 0 for multiplier in multipliers):
        raise ValueError("failure-charge multipliers must be non-negative")
    source_rows = payload.get("rows")
    if not isinstance(source_rows, list):
        raise ValueError("DeepSWE trial artifact missing rows list")
    scored_rows = [row for row in source_rows if _is_scored_deepswe_row(row)]
    analysis_rows = _prepare_analysis_rows(scored_rows, missing_cost_method)
    task_names = sorted({_required_str(row, "task_name") for row in analysis_rows})
    anchor_success_costs: dict[str, list[float]] = defaultdict(list)
    for row in analysis_rows:
        if row.get("config") == anchor_config and bool(row.get("passed")):
            anchor_success_costs[_required_str(row, "task_name")].append(
                float(row["_analysis_cost_usd"])
            )
    if not anchor_success_costs:
        raise ValueError(f"anchor configuration has no successful tasks: {anchor_config}")
    base_budgets = {
        task: median(costs) for task, costs in sorted(anchor_success_costs.items())
    }
    omitted_tasks = sorted(set(task_names) - set(base_budgets))
    common_basket_rows = [
        row
        for row in analysis_rows
        if _required_str(row, "task_name") in base_budgets
    ]

    scenarios = []
    for multiplier in multipliers:
        configurations = _summarize_failure_charge_scenario(
            common_basket_rows,
            base_budgets=base_budgets,
            multiplier=float(multiplier),
        )
        pass_ranks = _average_ranks(configurations, "pass_rate", reverse=True)
        cpsc_ranks = _average_ranks(
            configurations, "proxy_failure_charge_cpsc_usd", reverse=False
        )
        association_rows = []
        for row in configurations:
            config = str(row["config"])
            solved_tasks = {
                _required_str(source, "task_name")
                for source in common_basket_rows
                if source.get("config") == config and bool(source.get("passed"))
            }
            row["task_coverage_rate"] = len(solved_tasks) / len(base_budgets)
            row["pass_rate_rank"] = pass_ranks.get(config)
            row["proxy_failure_charge_cpsc_rank"] = cpsc_ranks.get(config)
            association_rows.append(
                {
                    "config": config,
                    "pass_rate_rank": pass_ranks.get(config),
                    "realized_cpsc_rank": cpsc_ranks.get(config),
                }
            )
        minimum = min(
            (
                row
                for row in configurations
                if row.get("proxy_failure_charge_cpsc_usd") is not None
            ),
            key=lambda row: (
                float(row["proxy_failure_charge_cpsc_usd"]),
                str(row["config"]),
            ),
            default=None,
        )
        scenarios.append(
            {
                "multiplier": float(multiplier),
                "minimum_cpsc_config": minimum.get("config") if minimum else None,
                "minimum_cpsc_usd": (
                    minimum.get("proxy_failure_charge_cpsc_usd")
                    if minimum
                    else None
                ),
                "rank_association": _rank_association(association_rows),
                "configurations": configurations,
            }
        )
    return {
        "schema_version": DEEPSWE_ECONOMICS_SCHEMA_VERSION,
        "status": "post_hoc_anchor_success_pseudo_budget_common_basket",
        "proxy_budget_construction": "median_anchor_success_spend_by_task",
        "anchor_config": anchor_config,
        "source_tasks": len(task_names),
        "common_basket_tasks": len(base_budgets),
        "anchor_unsolved_tasks": len(omitted_tasks),
        "omitted_task_names": omitted_tasks,
        "base_budget_definition": "median_anchor_success_spend_by_task",
        "base_budget_summary_usd": {
            "minimum": min(base_budgets.values()),
            "median": median(base_budgets.values()),
            "maximum": max(base_budgets.values()),
        },
        "scenarios": scenarios,
    }


def reconcile_deepswe_leaderboard(
    analysis: dict[str, object],
    leaderboard: dict[str, Any],
    *,
    tolerance: float = 1e-12,
) -> dict[str, object]:
    analysis_rows = {
        str(row["config"]): row for row in analysis.get("configurations", [])
    }
    leaderboard_rows = leaderboard.get("rows")
    if not isinstance(leaderboard_rows, list):
        raise ValueError("DeepSWE leaderboard artifact missing rows list")
    comparisons = []
    for official in leaderboard_rows:
        config = _required_str(official, "config")
        actual = analysis_rows.get(config)
        if actual is None:
            comparisons.append({"config": config, "issue": "missing_from_analysis"})
            continue
        official_pass_rate = float(official["pass_rate"])
        official_mean_cost = float(official["mean_cost_usd"])
        official_cpsc = (
            official_mean_cost / official_pass_rate if official_pass_rate else None
        )
        comparisons.append(
            {
                "config": config,
                "pass_rate_abs_diff": abs(
                    float(actual["pass_rate"]) - official_pass_rate
                ),
                "mean_cost_abs_diff": abs(
                    float(actual["mean_cost_per_attempt_usd"])
                    - official_mean_cost
                ),
                "realized_cpsc_abs_diff": (
                    abs(float(actual["realized_cpsc_usd"]) - official_cpsc)
                    if official_cpsc is not None
                    and actual.get("realized_cpsc_usd") is not None
                    else None
                ),
            }
        )
    numeric_rows = [row for row in comparisons if "issue" not in row]
    missing_analysis = sorted(set(analysis_rows) - {
        str(row.get("config")) for row in leaderboard_rows if isinstance(row, dict)
    })
    maxima = {
        field: max(float(row[field] or 0.0) for row in numeric_rows)
        if numeric_rows
        else None
        for field in (
            "pass_rate_abs_diff",
            "mean_cost_abs_diff",
            "realized_cpsc_abs_diff",
        )
    }
    issues = [row for row in comparisons if "issue" in row]
    return {
        "analysis_configurations": len(analysis_rows),
        "leaderboard_configurations": len(leaderboard_rows),
        "tolerance": tolerance,
        "maximum_absolute_differences": maxima,
        "missing_from_analysis": issues,
        "missing_from_leaderboard": missing_analysis,
        "all_match": (
            not issues
            and not missing_analysis
            and all(value is not None and value <= tolerance for value in maxima.values())
        ),
    }


def build_deepswe_economics_report(
    trials: dict[str, Any],
    leaderboard: dict[str, Any],
    plan: dict[str, Any],
    *,
    bootstrap_replicates: int | None = None,
) -> dict[str, object]:
    missing_plan = plan.get("missing_cost") or {}
    primary_name = str(missing_plan.get("primary") or "")
    primary_method = MISSING_COST_PLAN_NAMES.get(primary_name, primary_name)
    if primary_method not in MISSING_COST_METHODS:
        raise ValueError(f"unknown primary missing-cost plan: {primary_name}")
    primary = analyze_deepswe_trials(trials, missing_cost_method=primary_method)

    uncertainty = plan.get("uncertainty") or {}
    replicates = (
        bootstrap_replicates
        if bootstrap_replicates is not None
        else int(uncertainty["replicates"])
    )
    bootstrap = bootstrap_deepswe_trials(
        trials,
        replicates=replicates,
        seed=int(uncertainty["seed"]),
        missing_cost_method=primary_method,
    )

    sensitivity_names = [str(name) for name in missing_plan.get("sensitivities") or []]
    missing_sensitivities = []
    for name in sensitivity_names:
        method = MISSING_COST_PLAN_NAMES.get(name, name)
        sensitivity = analyze_deepswe_trials(trials, missing_cost_method=method)
        missing_sensitivities.append(
            {
                "name": name,
                "method": method,
                "rank_association": sensitivity["rank_association"],
                "configurations": sensitivity["configurations"],
                "reliability_floor_curve": sensitivity["reliability_floor_curve"],
            }
        )

    failure_plan = plan.get("counterfactual_failure_charge") or {}
    failure_sensitivity = analyze_failure_charge_sensitivity(
        trials,
        anchor_config=str(failure_plan["anchor_config"]),
        multipliers=tuple(float(value) for value in failure_plan["multipliers"]),
        missing_cost_method=primary_method,
    )
    anchor_success_sensitivity = analyze_anchor_success_budget_sensitivity(
        trials,
        anchor_config=str(failure_plan["anchor_config"]),
        multipliers=tuple(float(value) for value in failure_plan["multipliers"]),
        missing_cost_method=primary_method,
    )
    return {
        "schema_version": DEEPSWE_ECONOMICS_SCHEMA_VERSION,
        "plan_schema_version": plan.get("schema_version"),
        "benchmark_release": plan.get("benchmark_release"),
        "source_metadata": {
            "trial_scope": trials.get("scope"),
            "leaderboard_scope": leaderboard.get("scope"),
            "leaderboard_generated_at": leaderboard.get("generated_at"),
        },
        "provider_cost_provenance": _provider_cost_provenance(
            primary["configurations"]
        ),
        "primary": primary,
        "bootstrap": bootstrap,
        "missing_cost_sensitivities": missing_sensitivities,
        "failure_charge_sensitivity": failure_sensitivity,
        "anchor_success_budget_sensitivity": anchor_success_sensitivity,
        "leaderboard_reconciliation": reconcile_deepswe_leaderboard(
            primary, leaderboard
        ),
        "common_price_repricing": {
            "status": "not_run",
            "gate": (plan.get("common_price_repricing") or {}).get("status"),
        },
    }


def _provider_cost_provenance(
    configurations: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_provider: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in configurations:
        by_provider[str(row.get("provider") or "unknown")].append(row)
    return [
        {
            "provider_route": provider,
            "model_families": sorted(
                {str(row.get("model") or "unknown") for row in rows}
            ),
            "configurations": len(rows),
            "cost_field": "trial.cost_usd",
            "price_semantics_status": "provider_reported_not_common_price_reconciled",
        }
        for provider, rows in sorted(by_provider.items())
    ]


def _is_scored_deepswe_row(row: object) -> bool:
    return bool(
        _is_deepswe_full_row(row)
        and isinstance(row, dict)
        and row.get("included_in_score") is True
    )


def _is_deepswe_full_row(row: object) -> bool:
    return bool(
        isinstance(row, dict)
        and row.get("source") == "deep-swe"
        and row.get("eval_scope") == "full"
    )


def _prepare_analysis_rows(
    rows: list[dict[str, object]],
    method: str,
) -> list[dict[str, object]]:
    if method == "complete_case":
        return [
            _with_analysis_cost(row, float(row["cost_usd"]), False)
            for row in rows
            if row.get("cost_usd") is not None
        ]

    observed_by_config: dict[str, list[float]] = defaultdict(list)
    observed_by_config_outcome: dict[tuple[str, bool], list[float]] = defaultdict(list)
    for row in rows:
        config = _required_str(row, "config")
        cost = row.get("cost_usd")
        if cost is None:
            continue
        numeric_cost = float(cost)
        if numeric_cost < 0:
            raise ValueError(f"negative cost for trial {row.get('trial_name')}")
        passed = bool(row.get("passed"))
        observed_by_config[config].append(numeric_cost)
        observed_by_config_outcome[(config, passed)].append(numeric_cost)

    prepared = []
    for row in rows:
        cost = row.get("cost_usd")
        if cost is not None:
            prepared.append(_with_analysis_cost(row, float(cost), False))
            continue

        config = _required_str(row, "config")
        if method == "zero":
            imputed = 0.0
        elif method == "config_mean":
            candidates = observed_by_config[config]
            if not candidates:
                raise ValueError(f"cannot impute cost for configuration without observed costs: {config}")
            imputed = mean(candidates)
        else:
            candidates = observed_by_config_outcome[(config, bool(row.get("passed")))]
            if not candidates:
                raise ValueError(
                    "cannot impute outcome-specific cost for configuration without observed peers: "
                    f"{config}"
                )
            imputed = median(candidates)
        prepared.append(_with_analysis_cost(row, imputed, True))
    return prepared


def _with_analysis_cost(
    row: dict[str, object],
    cost: float,
    imputed: bool,
) -> dict[str, object]:
    prepared = dict(row)
    prepared["_analysis_cost_usd"] = cost
    prepared["_cost_imputed"] = imputed
    return prepared


def _summarize_configurations(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_config[_required_str(row, "config")].append(row)

    summaries = []
    for config, config_rows in sorted(by_config.items()):
        attempts = len(config_rows)
        successful = [row for row in config_rows if bool(row.get("passed"))]
        failed = [row for row in config_rows if not bool(row.get("passed"))]
        successes = len(successful)
        failures = len(failed)
        costs = [float(row["_analysis_cost_usd"]) for row in config_rows]
        successful_costs = [float(row["_analysis_cost_usd"]) for row in successful]
        failed_costs = [float(row["_analysis_cost_usd"]) for row in failed]
        total_cost = sum(costs)
        successful_mean = mean(successful_costs) if successful_costs else None
        failed_mean = mean(failed_costs) if failed_costs else None
        realized_cpsc = total_cost / successes if successes else None
        reliability_tax = (
            failures / successes * failed_mean
            if successes and failed_mean is not None
            else (0.0 if successes else None)
        )
        tax_share = (
            reliability_tax / realized_cpsc
            if reliability_tax is not None and realized_cpsc
            else (0.0 if realized_cpsc else None)
        )
        first = config_rows[0]
        summaries.append(
            {
                "config": config,
                "model": first.get("model"),
                "provider": first.get("provider"),
                "harness": first.get("harness"),
                "reasoning_effort": first.get("reasoning_effort"),
                "attempts": attempts,
                "successes": successes,
                "failures": failures,
                "pass_rate": successes / attempts if attempts else None,
                "observed_cost_rows": sum(
                    1 for row in config_rows if not bool(row["_cost_imputed"])
                ),
                "imputed_cost_rows": sum(
                    1 for row in config_rows if bool(row["_cost_imputed"])
                ),
                "total_cost_usd": total_cost,
                "mean_cost_per_attempt_usd": mean(costs) if costs else None,
                "conditional_successful_spend_usd": successful_mean,
                "conditional_failed_spend_usd": failed_mean,
                "realized_reliability_tax_usd": reliability_tax,
                "realized_reliability_tax_share": tax_share,
                "realized_cpsc_usd": realized_cpsc,
            }
        )
    return summaries


def _analyze_task_weighting_sensitivity(
    rows: list[dict[str, object]],
    *,
    pooled_configurations: list[dict[str, object]],
) -> dict[str, object]:
    """Compare observed-attempt pooling with an equal-task workload basket."""
    tasks = sorted({_required_str(row, "task_name") for row in rows})
    configs = sorted({_required_str(row, "config") for row in rows})
    tasks_by_config: dict[str, set[str]] = {config: set() for config in configs}
    for row in rows:
        tasks_by_config[_required_str(row, "config")].add(
            _required_str(row, "task_name")
        )
    common_tasks = set(tasks)
    for config in configs:
        common_tasks &= tasks_by_config[config]

    full_basket = _summarize_equal_task_configurations(
        rows,
        selected_tasks=set(tasks),
        declared_tasks=set(tasks),
    )
    _attach_equal_task_ranks_and_frontier(full_basket, require_full_basket=True)
    common_basket = _summarize_equal_task_configurations(
        rows,
        selected_tasks=common_tasks,
        declared_tasks=common_tasks,
    )
    _attach_equal_task_ranks_and_frontier(common_basket, require_full_basket=True)

    pooled_by_config = {
        str(row["config"]): row for row in pooled_configurations
    }
    for row in full_basket:
        pooled = pooled_by_config[str(row["config"])]
        row["observed_attempt_pass_rate"] = pooled.get("pass_rate")
        row["observed_attempt_cpsc_usd"] = pooled.get("realized_cpsc_usd")
        if row["full_basket_identified"] and pooled.get("realized_cpsc_usd"):
            row["cpsc_relative_difference"] = (
                float(row["equal_task_cpsc_usd"])
                / float(pooled["realized_cpsc_usd"])
                - 1.0
            )
        else:
            row["cpsc_relative_difference"] = None

    full_identified = [row for row in full_basket if row["full_basket_identified"]]
    return {
        "status": "declared_basket_sensitivity",
        "observed_attempt_estimand": "sum_cost_over_sum_successes",
        "equal_task_estimand": "mean_task_attempt_cost_over_mean_task_pass_rate",
        "declared_task_count": len(tasks),
        "full_basket_identified_configurations": len(full_identified),
        "incomplete_full_basket_configurations": [
            str(row["config"])
            for row in full_basket
            if not row["full_basket_identified"]
        ],
        "full_basket_configurations": full_basket,
        "full_basket_reliability_floor_curve": _equal_task_reliability_floor_curve(
            full_identified
        ),
        "common_basket_task_count": len(common_tasks),
        "common_basket_excluded_tasks": sorted(set(tasks) - common_tasks),
        "common_basket_configurations": common_basket,
        "common_basket_reliability_floor_curve": _equal_task_reliability_floor_curve(
            common_basket
        ),
    }


def _analyze_resource_intensity(
    rows: list[dict[str, object]],
    *,
    pooled_configurations: list[dict[str, object]],
) -> list[dict[str, object]]:
    resource_fields = dict(RESOURCE_FIELD_SPECS)
    pooled_by_config = {
        str(row["config"]): row for row in pooled_configurations
    }
    by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_config[_required_str(row, "config")].append(row)
    summaries = []
    for config, config_rows in sorted(by_config.items()):
        successes = sum(bool(row.get("passed")) for row in config_rows)
        pooled = pooled_by_config[config]
        summary: dict[str, object] = {
            "config": config,
            "model": pooled.get("model"),
            "provider": pooled.get("provider"),
            "harness": pooled.get("harness"),
            "reasoning_effort": pooled.get("reasoning_effort"),
            "attempts": len(config_rows),
            "successes": successes,
            "pass_rate": pooled.get("pass_rate"),
            "reported_cpsc_usd": pooled.get("realized_cpsc_usd"),
            "reported_cpsc_rank": pooled.get("realized_cpsc_rank"),
        }
        for output_field, source_field in resource_fields.items():
            values = [row.get(source_field) for row in config_rows]
            missing = sum(value is None for value in values)
            total = sum(float(value) for value in values if value is not None)
            summary[output_field] = (
                total / successes if successes and missing == 0 else None
            )
            summary[f"{source_field}_missing_rows"] = missing
        token_metrics = tuple(
            summary[field]
            for field in (
                "input_tokens_per_success",
                "cache_tokens_per_success",
                "output_tokens_per_success",
            )
        )
        summary["total_tokens_per_success"] = (
            sum(float(value) for value in token_metrics)
            if successes and all(value is not None for value in token_metrics)
            else None
        )
        summaries.append(summary)

    for field in RESOURCE_METRICS:
        ranks = _average_ranks(summaries, field, reverse=False)
        for row in summaries:
            row[f"{field}_rank"] = ranks.get(str(row["config"]))
            row[f"{field}_pareto_frontier"] = (
                row.get(field) is not None
                and row.get("pass_rate") is not None
                and not any(
                    other is not row
                    and other.get("pass_rate") is not None
                    and other.get(field) is not None
                    and float(other["pass_rate"]) >= float(row["pass_rate"])
                    and float(other[field]) <= float(row[field])
                    and (
                        float(other["pass_rate"]) > float(row["pass_rate"])
                        or float(other[field]) < float(row[field])
                    )
                    for other in summaries
                )
            )
    for row in summaries:
        row["reported_cpsc_pareto_frontier"] = (
            row.get("reported_cpsc_usd") is not None
            and row.get("pass_rate") is not None
            and not any(
                other is not row
                and other.get("pass_rate") is not None
                and other.get("reported_cpsc_usd") is not None
                and float(other["pass_rate"]) >= float(row["pass_rate"])
                and float(other["reported_cpsc_usd"])
                <= float(row["reported_cpsc_usd"])
                and (
                    float(other["pass_rate"]) > float(row["pass_rate"])
                    or float(other["reported_cpsc_usd"])
                    < float(row["reported_cpsc_usd"])
                )
                for other in summaries
            )
        )
    return summaries


def _summarize_equal_task_configurations(
    rows: list[dict[str, object]],
    *,
    selected_tasks: set[str],
    declared_tasks: set[str],
) -> list[dict[str, object]]:
    by_config_task: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        task = _required_str(row, "task_name")
        if task in selected_tasks:
            by_config_task[_required_str(row, "config")][task].append(row)

    summaries = []
    configs = sorted({_required_str(row, "config") for row in rows})
    for config in configs:
        task_rows = by_config_task[config]
        task_pass_rates = []
        task_mean_costs = []
        for task in sorted(selected_tasks):
            attempts = task_rows.get(task, [])
            if not attempts:
                continue
            task_pass_rates.append(
                sum(bool(row.get("passed")) for row in attempts) / len(attempts)
            )
            task_mean_costs.append(
                mean(float(row["_analysis_cost_usd"]) for row in attempts)
            )
        observed_tasks = set(task_rows)
        equal_task_pass_rate = mean(task_pass_rates) if task_pass_rates else None
        equal_task_mean_cost = mean(task_mean_costs) if task_mean_costs else None
        equal_task_cpsc = (
            equal_task_mean_cost / equal_task_pass_rate
            if equal_task_mean_cost is not None and equal_task_pass_rate
            else None
        )
        config_rows = [row for task in task_rows.values() for row in task]
        first = config_rows[0] if config_rows else next(
            row for row in rows if _required_str(row, "config") == config
        )
        missing_tasks = declared_tasks - observed_tasks
        summaries.append(
            {
                "config": config,
                "model": first.get("model"),
                "provider": first.get("provider"),
                "harness": first.get("harness"),
                "reasoning_effort": first.get("reasoning_effort"),
                "declared_task_count": len(declared_tasks),
                "observed_task_count": len(observed_tasks),
                "missing_task_count": len(missing_tasks),
                "missing_tasks": sorted(missing_tasks),
                "full_basket_identified": not missing_tasks,
                "equal_task_pass_rate": equal_task_pass_rate,
                "equal_task_mean_cost_per_attempt_usd": equal_task_mean_cost,
                "equal_task_cpsc_usd": equal_task_cpsc,
            }
        )
    return summaries


def _attach_equal_task_ranks_and_frontier(
    rows: list[dict[str, object]],
    *,
    require_full_basket: bool,
) -> None:
    eligible = [
        row
        for row in rows
        if (not require_full_basket or row["full_basket_identified"])
        and row.get("equal_task_pass_rate") is not None
        and row.get("equal_task_cpsc_usd") is not None
    ]
    pass_ranks = _average_ranks(eligible, "equal_task_pass_rate", reverse=True)
    cpsc_ranks = _average_ranks(eligible, "equal_task_cpsc_usd", reverse=False)
    for row in rows:
        config = str(row["config"])
        row["equal_task_pass_rate_rank"] = pass_ranks.get(config)
        row["equal_task_cpsc_rank"] = cpsc_ranks.get(config)
        pass_rank = pass_ranks.get(config)
        cpsc_rank = cpsc_ranks.get(config)
        row["equal_task_rank_displacement"] = (
            cpsc_rank - pass_rank
            if pass_rank is not None and cpsc_rank is not None
            else None
        )
        row["equal_task_attempt_cost_pareto_frontier"] = False
    for candidate in eligible:
        candidate_pass = float(candidate["equal_task_pass_rate"])
        candidate_cost = float(candidate["equal_task_mean_cost_per_attempt_usd"])
        candidate["equal_task_attempt_cost_pareto_frontier"] = not any(
            other is not candidate
            and float(other["equal_task_pass_rate"]) >= candidate_pass
            and float(other["equal_task_mean_cost_per_attempt_usd"]) <= candidate_cost
            and (
                float(other["equal_task_pass_rate"]) > candidate_pass
                or float(other["equal_task_mean_cost_per_attempt_usd"]) < candidate_cost
            )
            for other in eligible
        )


def _equal_task_reliability_floor_curve(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    curve = []
    for floor in DEFAULT_RELIABILITY_FLOORS:
        eligible = [
            row
            for row in rows
            if row.get("equal_task_pass_rate") is not None
            and float(row["equal_task_pass_rate"]) >= floor
            and row.get("equal_task_cpsc_usd") is not None
        ]
        best = min(
            eligible,
            key=lambda row: (float(row["equal_task_cpsc_usd"]), str(row["config"])),
            default=None,
        )
        curve.append(
            {
                "minimum_pass_rate": floor,
                "eligible_configurations": len(eligible),
                "minimum_cpsc_config": best.get("config") if best else None,
                "minimum_cpsc_usd": best.get("equal_task_cpsc_usd") if best else None,
                "observed_pass_rate": best.get("equal_task_pass_rate") if best else None,
            }
        )
    return curve


def _analyze_task_mix(rows: list[dict[str, object]]) -> dict[str, object]:
    tasks = sorted({_required_str(row, "task_name") for row in rows})
    configs = sorted({_required_str(row, "config") for row in rows})
    by_config_task: dict[str, dict[str, list[dict[str, object]]]] = {
        config: defaultdict(list) for config in configs
    }
    for row in rows:
        by_config_task[_required_str(row, "config")][
            _required_str(row, "task_name")
        ].append(row)

    solved_tasks: dict[str, set[str]] = {}
    heterogeneity = []
    for config in configs:
        task_rows = by_config_task[config]
        solved = {
            task
            for task, attempts in task_rows.items()
            if any(bool(row.get("passed")) for row in attempts)
        }
        solved_tasks[config] = solved
        complete = [attempts for attempts in task_rows.values() if len(attempts) == 4]
        success_counts = [sum(bool(row.get("passed")) for row in attempts) for attempts in complete]
        heterogeneity.append(
            {
                "config": config,
                "tasks_in_suite": len(tasks),
                "tasks_with_scored_attempts": len(task_rows),
                "no_scored_attempt_tasks": len(tasks) - len(task_rows),
                "complete_four_attempt_tasks": len(complete),
                "incomplete_scored_attempt_tasks": sum(
                    len(attempts) != 4 for attempts in task_rows.values()
                ),
                "zero_of_four_tasks": sum(count == 0 for count in success_counts),
                "one_to_three_of_four_tasks": sum(1 <= count <= 3 for count in success_counts),
                "four_of_four_tasks": sum(count == 4 for count in success_counts),
                "tasks_with_any_success": len(solved),
                "task_coverage_rate": len(solved) / len(tasks) if tasks else None,
            }
        )

    matched = []
    for index, config_a in enumerate(configs):
        for config_b in configs[index + 1 :]:
            solved_a = solved_tasks[config_a]
            solved_b = solved_tasks[config_b]
            intersection = solved_a & solved_b
            union = solved_a | solved_b
            metrics_a = _summarize_matched_task_rows(
                by_config_task[config_a], intersection
            )
            metrics_b = _summarize_matched_task_rows(
                by_config_task[config_b], intersection
            )
            row: dict[str, object] = {
                "config_a": config_a,
                "config_b": config_b,
                "config_a_solved_tasks": len(solved_a),
                "config_b_solved_tasks": len(solved_b),
                "matched_tasks": len(intersection),
                "solved_task_union": len(union),
                "solved_task_jaccard": len(intersection) / len(union) if union else None,
            }
            row.update({f"config_a_matched_{key}": value for key, value in metrics_a.items()})
            row.update({f"config_b_matched_{key}": value for key, value in metrics_b.items()})
            matched.append(row)

    return {
        "success_heterogeneity": heterogeneity,
        "matched_solved_task_comparisons": matched,
        "panel_solvedness_strata": _analyze_panel_solvedness_strata(
            rows,
            tasks=tasks,
            configs=configs,
        ),
        "leave_one_family_out_panel_solvedness": (
            _analyze_leave_one_family_out_panel_solvedness(rows, tasks=tasks)
        ),
        "gpt_5_6_group_out_panel_solvedness": _analyze_excluded_model_group(
            rows,
            tasks=tasks,
            excluded_models={"gpt-5-6-luna", "gpt-5-6-sol", "gpt-5-6-terra"},
            group_name="gpt-5-6",
        ),
        "matched_task_definition": "intersection_of_tasks_with_at_least_one_scored_success",
        "matched_task_interpretation": "post_outcome_diagnostic_not_causal_adjustment",
        "sequential_retry_policy": {
            "status": "not_identified_from_public_trial_rows",
            "reason": (
                "Trial IDs and timestamps do not define a predeclared retry order or a "
                "stopping policy. Empirical any-success task coverage is reported instead."
            ),
        },
    }


def _analyze_panel_solvedness_strata(
    rows: list[dict[str, object]],
    *,
    tasks: list[str],
    configs: list[str],
) -> dict[str, object]:
    config_count = len(configs)
    rare_max = max(1, config_count // 2)
    common_min = int(config_count * 0.75) + 1
    solved_by_task: dict[str, set[str]] = {task: set() for task in tasks}
    for row in rows:
        if bool(row.get("passed")):
            solved_by_task[_required_str(row, "task_name")].add(
                _required_str(row, "config")
            )

    task_rows = []
    tasks_by_stratum: dict[str, set[str]] = {
        "rare": set(),
        "contested": set(),
        "common": set(),
    }
    for task in tasks:
        solving_configurations = len(solved_by_task[task])
        if solving_configurations <= rare_max:
            stratum = "rare"
        elif solving_configurations < common_min:
            stratum = "contested"
        else:
            stratum = "common"
        tasks_by_stratum[stratum].add(task)
        task_rows.append(
            {
                "task_name": task,
                "panel_solving_configurations": solving_configurations,
                "panel_configurations": config_count,
                "stratum": stratum,
            }
        )

    configuration_rows = []
    summaries = []
    for stratum in ("rare", "contested", "common"):
        selected_tasks = tasks_by_stratum[stratum]
        stratum_rows = [
            row for row in rows if _required_str(row, "task_name") in selected_tasks
        ]
        configurations = _summarize_configurations(stratum_rows)
        _attach_ranks(configurations)
        by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in stratum_rows:
            by_config[_required_str(row, "config")].append(row)
        for configuration in configurations:
            config = str(configuration["config"])
            solved_tasks = {
                _required_str(row, "task_name")
                for row in by_config[config]
                if bool(row.get("passed"))
            }
            configuration.update(
                {
                    "stratum": stratum,
                    "tasks_in_stratum": len(selected_tasks),
                    "tasks_with_any_success": len(solved_tasks),
                    "task_coverage_rate": (
                        len(solved_tasks) / len(selected_tasks)
                        if selected_tasks
                        else None
                    ),
                }
            )
            configuration_rows.append(configuration)
        solving_counts = [len(solved_by_task[task]) for task in selected_tasks]
        summaries.append(
            {
                "stratum": stratum,
                "tasks": len(selected_tasks),
                "minimum_panel_solving_configurations": (
                    min(solving_counts) if solving_counts else None
                ),
                "maximum_panel_solving_configurations": (
                    max(solving_counts) if solving_counts else None
                ),
                "configurations": len(configurations),
                "defined_cpsc_configurations": sum(
                    row.get("realized_cpsc_usd") is not None
                    for row in configurations
                ),
                "rank_association": _rank_association(configurations),
            }
        )
    return {
        "status": "result_informed_panel_solvedness_diagnostic",
        "definition": (
            "Strata are defined from how many evaluated configurations solve each task. "
            "They are outcome-derived diagnostics, not preregistered task difficulty or "
            "ShallowSWE pressure labels."
        ),
        "definitions": [
            {
                "stratum": "rare",
                "minimum_panel_solving_configurations": 0,
                "maximum_panel_solving_configurations": rare_max,
            },
            {
                "stratum": "contested",
                "minimum_panel_solving_configurations": rare_max + 1,
                "maximum_panel_solving_configurations": common_min - 1,
            },
            {
                "stratum": "common",
                "minimum_panel_solving_configurations": common_min,
                "maximum_panel_solving_configurations": config_count,
            },
        ],
        "tasks": task_rows,
        "summaries": summaries,
        "configurations": configuration_rows,
    }


def _analyze_leave_one_family_out_panel_solvedness(
    rows: list[dict[str, object]],
    *,
    tasks: list[str],
) -> dict[str, object]:
    models = sorted({_required_str(row, "model") for row in rows})
    assignments = []
    configuration_rows = []
    for target_model in models:
        target_rows = [row for row in rows if row.get("model") == target_model]
        panel_rows = [row for row in rows if row.get("model") != target_model]
        target_configs = sorted(
            {_required_str(row, "config") for row in target_rows}
        )
        panel_configs = sorted({_required_str(row, "config") for row in panel_rows})
        panel_count = len(panel_configs)
        rare_max = max(1, panel_count // 2)
        common_min = int(panel_count * 0.75) + 1
        solved_by_task: dict[str, set[str]] = {task: set() for task in tasks}
        for row in panel_rows:
            if bool(row.get("passed")):
                solved_by_task[_required_str(row, "task_name")].add(
                    _required_str(row, "config")
                )
        tasks_by_stratum: dict[str, set[str]] = {
            "rare": set(),
            "contested": set(),
            "common": set(),
        }
        for task in tasks:
            solving = len(solved_by_task[task])
            if solving <= rare_max:
                stratum = "rare"
            elif solving < common_min:
                stratum = "contested"
            else:
                stratum = "common"
            tasks_by_stratum[stratum].add(task)
            assignments.append(
                {
                    "target_model_family": target_model,
                    "task_name": task,
                    "comparison_panel_configurations": panel_count,
                    "panel_solving_configurations": solving,
                    "stratum": stratum,
                }
            )
        for stratum in ("rare", "contested", "common"):
            selected_tasks = tasks_by_stratum[stratum]
            selected_rows = [
                row
                for row in target_rows
                if _required_str(row, "task_name") in selected_tasks
            ]
            if not selected_rows:
                continue
            summaries = _summarize_configurations(selected_rows)
            _attach_ranks(summaries)
            by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in selected_rows:
                by_config[_required_str(row, "config")].append(row)
            for summary in summaries:
                config = str(summary["config"])
                solved_tasks = {
                    _required_str(row, "task_name")
                    for row in by_config[config]
                    if bool(row.get("passed"))
                }
                summary.update(
                    {
                        "target_model_family": target_model,
                        "target_family_configurations": len(target_configs),
                        "comparison_panel_configurations": panel_count,
                        "stratum": stratum,
                        "tasks_in_stratum": len(selected_tasks),
                        "tasks_with_any_success": len(solved_tasks),
                        "task_coverage_rate": (
                            len(solved_tasks) / len(selected_tasks)
                            if selected_tasks
                            else None
                        ),
                    }
                )
                configuration_rows.append(summary)
    return {
        "status": "result_informed_leave_one_family_out_diagnostic",
        "definition": (
            "Each target model family's task strata are assigned using only outcomes from "
            "configurations outside that family. This removes the target family's own outcomes "
            "from its panel-solvedness labels."
        ),
        "model_families": len(models),
        "assignments": assignments,
        "configurations": configuration_rows,
    }


def _analyze_excluded_model_group(
    rows: list[dict[str, object]],
    *,
    tasks: list[str],
    excluded_models: set[str],
    group_name: str,
) -> dict[str, object]:
    target_rows = [row for row in rows if row.get("model") in excluded_models]
    panel_rows = [row for row in rows if row.get("model") not in excluded_models]
    panel_configs = sorted({_required_str(row, "config") for row in panel_rows})
    panel_count = len(panel_configs)
    rare_max = max(1, panel_count // 2)
    common_min = int(panel_count * 0.75) + 1
    solved_by_task: dict[str, set[str]] = {task: set() for task in tasks}
    for row in panel_rows:
        if bool(row.get("passed")):
            solved_by_task[_required_str(row, "task_name")].add(
                _required_str(row, "config")
            )
    tasks_by_stratum: dict[str, set[str]] = {
        "rare": set(),
        "contested": set(),
        "common": set(),
    }
    assignments = []
    for task in tasks:
        solving = len(solved_by_task[task])
        if solving <= rare_max:
            stratum = "rare"
        elif solving < common_min:
            stratum = "contested"
        else:
            stratum = "common"
        tasks_by_stratum[stratum].add(task)
        assignments.append(
            {
                "excluded_model_group": group_name,
                "task_name": task,
                "comparison_panel_configurations": panel_count,
                "panel_solving_configurations": solving,
                "stratum": stratum,
            }
        )

    configuration_rows = []
    for stratum in ("rare", "contested", "common"):
        selected_tasks = tasks_by_stratum[stratum]
        selected_rows = [
            row
            for row in target_rows
            if _required_str(row, "task_name") in selected_tasks
        ]
        summaries = _summarize_configurations(selected_rows)
        _attach_ranks(summaries)
        by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in selected_rows:
            by_config[_required_str(row, "config")].append(row)
        for summary in summaries:
            config = str(summary["config"])
            solved_tasks = {
                _required_str(row, "task_name")
                for row in by_config[config]
                if bool(row.get("passed"))
            }
            summary.update(
                {
                    "excluded_model_group": group_name,
                    "comparison_panel_configurations": panel_count,
                    "stratum": stratum,
                    "tasks_in_stratum": len(selected_tasks),
                    "tasks_with_any_success": len(solved_tasks),
                    "task_coverage_rate": (
                        len(solved_tasks) / len(selected_tasks)
                        if selected_tasks
                        else None
                    ),
                }
            )
            configuration_rows.append(summary)
    return {
        "status": "result_informed_group_out_panel_solvedness_diagnostic",
        "excluded_model_group": group_name,
        "excluded_model_families": sorted(excluded_models),
        "comparison_panel_configurations": panel_count,
        "definition": (
            "Task strata are assigned using only configurations outside the excluded model "
            "group, so every configuration in the group is evaluated on the same labels and "
            "none contributes to those labels."
        ),
        "assignments": assignments,
        "configurations": configuration_rows,
    }


def _summarize_matched_task_rows(
    by_task: dict[str, list[dict[str, object]]],
    selected_tasks: set[str],
) -> dict[str, object]:
    rows = [row for task in selected_tasks for row in by_task.get(task, [])]
    attempts = len(rows)
    successes = sum(bool(row.get("passed")) for row in rows)
    total_cost = sum(float(row["_analysis_cost_usd"]) for row in rows)
    return {
        "attempts": attempts,
        "successes": successes,
        "pass_rate": successes / attempts if attempts else None,
        "total_cost_usd": total_cost,
        "cpsc_usd": total_cost / successes if successes else None,
    }


def _audit_infrastructure_exclusions(
    source_rows: list[dict[str, object]],
    analysis_rows: list[dict[str, object]],
) -> dict[str, object]:
    candidate_rows = [row for row in source_rows if _is_deepswe_full_row(row)]
    excluded_rows = [row for row in candidate_rows if row.get("included_in_score") is not True]
    source_by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
    included_by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in candidate_rows:
        source_by_config[_required_str(row, "config")].append(row)
    for row in analysis_rows:
        included_by_config[_required_str(row, "config")].append(row)

    configurations = []
    for config, config_source_rows in sorted(source_by_config.items()):
        included = included_by_config.get(config, [])
        excluded = [
            row for row in config_source_rows if row.get("included_in_score") is not True
        ]
        successes = sum(bool(row.get("passed")) for row in included)
        included_costs = [float(row["_analysis_cost_usd"]) for row in included]
        included_total_cost = sum(included_costs)
        included_mean_cost = mean(included_costs) if included_costs else None
        excluded_observed_costs = [
            float(row["cost_usd"])
            for row in excluded
            if row.get("cost_usd") is not None
        ]
        excluded_missing_cost = sum(row.get("cost_usd") is None for row in excluded)
        observed_cost_total = sum(excluded_observed_costs)
        config_mean_scenario_total = (
            included_total_cost
            + observed_cost_total
            + excluded_missing_cost * included_mean_cost
            if included_mean_cost is not None
            else None
        )
        by_task: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in config_source_rows:
            by_task[_required_str(row, "task_name")].append(row)
        configurations.append(
            {
                "config": config,
                "source_attempts": len(config_source_rows),
                "included_attempts": len(included),
                "excluded_attempts": len(excluded),
                "excluded_task_cells": len(
                    {_required_str(row, "task_name") for row in excluded}
                ),
                "tasks_with_all_attempts_excluded": sum(
                    all(row.get("included_in_score") is not True for row in task_rows)
                    for task_rows in by_task.values()
                ),
                "excluded_reported_cost_rows": len(excluded_observed_costs),
                "excluded_missing_cost_rows": excluded_missing_cost,
                "excluded_reported_cost_usd": observed_cost_total,
                "excluded_error_categories": dict(
                    sorted(
                        Counter(
                            str(row.get("error_category") or "unknown") for row in excluded
                        ).items()
                    )
                ),
                "included_successes": successes,
                "included_pass_rate": successes / len(included) if included else None,
                "exclusions_as_failures_pass_rate": (
                    successes / len(config_source_rows) if config_source_rows else None
                ),
                "included_cpsc_usd": (
                    included_total_cost / successes if successes else None
                ),
                "exclusions_as_failures_observed_cost_cpsc_lower_bound_usd": (
                    (included_total_cost + observed_cost_total) / successes
                    if successes
                    else None
                ),
                "exclusions_as_failures_config_mean_cost_cpsc_usd": (
                    config_mean_scenario_total / successes
                    if successes and config_mean_scenario_total is not None
                    else None
                ),
                "exclusions_as_failures_config_mean_attempt_cost_usd": (
                    config_mean_scenario_total / len(config_source_rows)
                    if config_source_rows and config_mean_scenario_total is not None
                    else None
                ),
            }
        )

    included_scenario = [
        {
            "config": row["config"],
            "pass_rate": row["included_pass_rate"],
            "realized_cpsc_usd": row["included_cpsc_usd"],
            "mean_cost_per_attempt_usd": (
                float(row["included_cpsc_usd"]) * float(row["included_pass_rate"])
                if row.get("included_cpsc_usd") is not None
                and row.get("included_pass_rate") is not None
                else None
            ),
        }
        for row in configurations
    ]
    config_mean_scenario = [
        {
            "config": row["config"],
            "pass_rate": row["exclusions_as_failures_pass_rate"],
            "realized_cpsc_usd": row[
                "exclusions_as_failures_config_mean_cost_cpsc_usd"
            ],
            "mean_cost_per_attempt_usd": row[
                "exclusions_as_failures_config_mean_attempt_cost_usd"
            ],
        }
        for row in configurations
    ]
    for scenario in (included_scenario, config_mean_scenario):
        _attach_ranks(scenario)
        _attach_attempt_cost_frontier(scenario)
    included_by_name = {str(row["config"]): row for row in included_scenario}
    config_mean_by_name = {str(row["config"]): row for row in config_mean_scenario}
    for row in configurations:
        config = str(row["config"])
        included_row = included_by_name[config]
        config_mean_row = config_mean_by_name[config]
        row["included_cpsc_rank"] = included_row.get("realized_cpsc_rank")
        row["config_mean_cpsc_rank"] = config_mean_row.get("realized_cpsc_rank")
        row["config_mean_cpsc_rank_change"] = (
            float(config_mean_row["realized_cpsc_rank"])
            - float(included_row["realized_cpsc_rank"])
            if config_mean_row.get("realized_cpsc_rank") is not None
            and included_row.get("realized_cpsc_rank") is not None
            else None
        )
        row["included_attempt_cost_pareto_frontier"] = included_row.get(
            "attempt_cost_pareto_frontier"
        )
        row["config_mean_attempt_cost_pareto_frontier"] = config_mean_row.get(
            "attempt_cost_pareto_frontier"
        )

    rank_change_rows = [
        row for row in configurations if row.get("config_mean_cpsc_rank_change") is not None
    ]
    largest_rank_change = max(
        rank_change_rows,
        key=lambda row: abs(float(row["config_mean_cpsc_rank_change"])),
        default=None,
    )
    frontier_changes = [
        str(row["config"])
        for row in configurations
        if row.get("included_attempt_cost_pareto_frontier")
        != row.get("config_mean_attempt_cost_pareto_frontier")
    ]
    return {
        "status": "retrospective_sensitivity_not_primary_cohort",
        "source_rows": len(candidate_rows),
        "included_rows": len(candidate_rows) - len(excluded_rows),
        "excluded_rows": len(excluded_rows),
        "excluded_error_categories": dict(
            sorted(
                Counter(
                    str(row.get("error_category") or "unknown") for row in excluded_rows
                ).items()
            )
        ),
        "maximum_cpsc_rank_change": (
            abs(float(largest_rank_change["config_mean_cpsc_rank_change"]))
            if largest_rank_change is not None
            else None
        ),
        "maximum_cpsc_rank_change_config": (
            largest_rank_change.get("config") if largest_rank_change else None
        ),
        "attempt_cost_frontier_membership_changes": frontier_changes,
        "attempt_cost_frontier_membership_change_count": len(frontier_changes),
        "config_mean_reliability_floor_curve": _reliability_floor_curve(
            config_mean_scenario
        ),
        "configurations": configurations,
    }


def _task_stat_matrix(
    rows: list[dict[str, object]],
    *,
    configs: list[str],
    tasks: list[str],
) -> dict[str, list[tuple[int, int, int, float, float, float]]]:
    task_indexes = {task: index for index, task in enumerate(tasks)}
    stats: dict[str, list[list[float]]] = {
        config: [[0.0] * 6 for _ in tasks] for config in configs
    }
    for row in rows:
        config = _required_str(row, "config")
        task_index = task_indexes[_required_str(row, "task_name")]
        passed = bool(row.get("passed"))
        cost = float(row["_analysis_cost_usd"])
        values = stats[config][task_index]
        values[0] += 1
        values[1] += int(passed)
        values[2] += int(not passed)
        values[3] += cost
        values[4] += cost if passed else 0.0
        values[5] += cost if not passed else 0.0
    return {
        config: [
            (
                int(values[0]),
                int(values[1]),
                int(values[2]),
                values[3],
                values[4],
                values[5],
            )
            for values in config_stats
        ]
        for config, config_stats in stats.items()
    }


def _task_resource_matrix(
    rows: list[dict[str, object]],
    *,
    configs: list[str],
    tasks: list[str],
) -> dict[str, list[tuple[float, ...]]]:
    task_indexes = {task: index for index, task in enumerate(tasks)}
    stats: dict[str, list[list[float]]] = {
        config: [[0.0] * (1 + len(RESOURCE_FIELD_SPECS)) for _ in tasks]
        for config in configs
    }
    for row in rows:
        config = _required_str(row, "config")
        task_index = task_indexes[_required_str(row, "task_name")]
        values = stats[config][task_index]
        values[0] += int(bool(row.get("passed")))
        for index, (_, field) in enumerate(RESOURCE_FIELD_SPECS, start=1):
            value = row.get(field)
            values[index] += float(value) if value is not None else 0.0
    return {
        config: [tuple([int(values[0]), *values[1:]]) for values in config_stats]
        for config, config_stats in stats.items()
    }


def _bootstrap_metrics(
    task_stats: list[tuple[int, int, int, float, float, float]],
    task_counts: list[int],
) -> dict[str, float | None]:
    attempts = 0
    successes = 0
    failures = 0
    total_cost = 0.0
    successful_cost = 0.0
    failed_cost = 0.0
    for count, values in zip(task_counts, task_stats, strict=True):
        if not count:
            continue
        attempts += count * values[0]
        successes += count * values[1]
        failures += count * values[2]
        total_cost += count * values[3]
        successful_cost += count * values[4]
        failed_cost += count * values[5]
    realized_cpsc = total_cost / successes if successes else None
    return {
        "pass_rate": successes / attempts if attempts else None,
        "realized_cpsc_usd": realized_cpsc,
        "conditional_successful_spend_usd": (
            successful_cost / successes if successes else None
        ),
        "conditional_failed_spend_usd": failed_cost / failures if failures else None,
        "realized_reliability_tax_usd": failed_cost / successes if successes else None,
        "realized_reliability_tax_share": (
            failed_cost / total_cost if total_cost else None
        ),
    }


def _bootstrap_resource_metrics(
    task_stats: list[tuple[float, ...]],
    task_counts: list[int],
) -> dict[str, float | None]:
    successes = 0
    totals = [0.0] * len(RESOURCE_FIELD_SPECS)
    for count, values in zip(task_counts, task_stats, strict=True):
        if not count:
            continue
        successes += count * values[0]
        for index in range(len(RESOURCE_FIELD_SPECS)):
            totals[index] += count * values[index + 1]
    fields = tuple(field for field, _ in RESOURCE_FIELD_SPECS)
    metrics = {
        field: total / successes if successes else None
        for field, total in zip(fields, totals, strict=True)
    }
    metrics["total_tokens_per_success"] = (
        sum(totals[1:4]) / successes if successes else None
    )
    return metrics


def _paired_resource_comparisons(
    configs: list[str],
    samples: dict[str, dict[str, list[float | None]]],
    *,
    point_resources: list[dict[str, object]],
) -> list[dict[str, object]]:
    point_by_config = {str(row["config"]): row for row in point_resources}
    comparisons = []
    for index, config_a in enumerate(configs):
        for config_b in configs[index + 1 :]:
            for field in RESOURCE_METRICS:
                ratios = [
                    float(value_a) / float(value_b)
                    for value_a, value_b in zip(
                        samples[config_a][field],
                        samples[config_b][field],
                        strict=True,
                    )
                    if value_a is not None
                    and value_b is not None
                    and float(value_b) > 0
                ]
                low, high = _interval(ratios)
                point_a = point_by_config[config_a].get(field)
                point_b = point_by_config[config_b].get(field)
                comparisons.append(
                    {
                        "config_a": config_a,
                        "config_b": config_b,
                        "resource_metric": field,
                        "point_ratio_a_over_b": (
                            float(point_a) / float(point_b)
                            if point_a is not None
                            and point_b is not None
                            and float(point_b) > 0
                            else None
                        ),
                        "ratio_ci_low": low,
                        "ratio_ci_high": high,
                        "defined_replicates": len(ratios),
                        "a_lower_replicates": sum(ratio < 1.0 for ratio in ratios),
                        "a_lower_share": (
                            sum(ratio < 1.0 for ratio in ratios) / len(ratios)
                            if ratios
                            else None
                        ),
                    }
                )
    return comparisons


def _bootstrap_equal_task_weighting_sensitivity(
    matrix: dict[str, list[tuple[int, int, int, float, float, float]]],
    *,
    configs: list[str],
    tasks: list[str],
    point_configurations: list[dict[str, object]],
    analysis_rows: list[dict[str, object]],
    replicates: int,
    seed: int,
) -> dict[str, object]:
    point_sensitivity = _analyze_task_weighting_sensitivity(
        analysis_rows,
        pooled_configurations=point_configurations,
    )
    point_rows = [
        row
        for row in point_sensitivity["full_basket_configurations"]
        if row["full_basket_identified"]
    ]
    complete_configs = [str(row["config"]) for row in point_rows]
    point_curve = {
        float(row["minimum_pass_rate"]): row
        for row in _equal_task_reliability_floor_curve(point_rows)
    }
    pass_samples: dict[str, list[float | None]] = {
        config: [] for config in complete_configs
    }
    cpsc_samples: dict[str, list[float | None]] = {
        config: [] for config in complete_configs
    }
    floor_winners: dict[float, list[str | None]] = {
        floor: [] for floor in DEFAULT_RELIABILITY_FLOORS
    }

    random = Random(seed)
    for _ in range(replicates):
        task_counts = [0] * len(tasks)
        for _ in tasks:
            task_counts[random.randrange(len(tasks))] += 1
        replicate_rows = []
        for config in complete_configs:
            metrics = _bootstrap_equal_task_metrics(matrix[config], task_counts)
            pass_samples[config].append(metrics["equal_task_pass_rate"])
            cpsc_samples[config].append(metrics["equal_task_cpsc_usd"])
            replicate_rows.append({"config": config, **metrics})
        for row in _equal_task_reliability_floor_curve(replicate_rows):
            floor = float(row["minimum_pass_rate"])
            winner = row.get("minimum_cpsc_config")
            floor_winners[floor].append(str(winner) if winner is not None else None)

    policies = []
    frequencies = []
    for floor in DEFAULT_RELIABILITY_FLOORS:
        winners = floor_winners[floor]
        counts = Counter(winner for winner in winners if winner is not None)
        defined = sum(counts.values())
        point_value = point_curve[floor].get("minimum_cpsc_config")
        point_winner = str(point_value) if point_value is not None else None
        point_pass_samples = pass_samples.get(point_winner, [])
        point_meets = sum(
            value is not None and float(value) >= floor
            for value in point_pass_samples
        )
        point_defined = sum(value is not None for value in point_pass_samples)
        most_selected = min(
            counts,
            key=lambda config: (-counts[config], config),
            default=None,
        )
        policies.append(
            {
                "minimum_pass_rate": floor,
                "point_estimate_winner": point_winner,
                "selection_defined_replicates": defined,
                "no_eligible_configuration_replicates": replicates - defined,
                "point_winner_selection_count": counts.get(point_winner, 0),
                "point_winner_selection_share_all_replicates": (
                    counts.get(point_winner, 0) / replicates
                    if point_winner is not None
                    else None
                ),
                "point_winner_selection_share_when_defined": (
                    counts.get(point_winner, 0) / defined
                    if point_winner is not None and defined
                    else None
                ),
                "point_winner_meets_floor_bootstrap_share": (
                    point_meets / point_defined if point_defined else None
                ),
                "most_selected_config": most_selected,
                "most_selected_count": counts.get(most_selected, 0),
                "most_selected_share_all_replicates": (
                    counts.get(most_selected, 0) / replicates
                    if most_selected is not None
                    else None
                ),
                "most_selected_share_when_defined": (
                    counts.get(most_selected, 0) / defined
                    if most_selected is not None and defined
                    else None
                ),
            }
        )
        for config, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        ):
            frequencies.append(
                {
                    "minimum_pass_rate": floor,
                    "config": config,
                    "selection_count": count,
                    "selection_share_all_replicates": count / replicates,
                    "selection_share_when_defined": count / defined if defined else None,
                }
            )

    configuration_intervals = []
    for config in complete_configs:
        pass_low, pass_high = _interval(pass_samples[config])
        cpsc_low, cpsc_high = _interval(cpsc_samples[config])
        configuration_intervals.append(
            {
                "config": config,
                "pass_rate_ci_low": pass_low,
                "pass_rate_ci_high": pass_high,
                "realized_cpsc_usd_ci_low": cpsc_low,
                "realized_cpsc_usd_ci_high": cpsc_high,
                "defined_cpsc_replicates": sum(
                    value is not None for value in cpsc_samples[config]
                ),
            }
        )
    return {
        "status": "declared_basket_sensitivity",
        "task_weighting": "equal_task",
        "complete_basket_configurations": len(complete_configs),
        "incomplete_basket_configurations": sorted(set(configs) - set(complete_configs)),
        "configurations": configuration_intervals,
        "reliability_floor_policy": policies,
        "reliability_floor_selection_frequencies": frequencies,
    }


def _bootstrap_equal_task_metrics(
    task_stats: list[tuple[int, int, int, float, float, float]],
    task_counts: list[int],
) -> dict[str, float | None]:
    selected_tasks = 0
    pass_rate_total = 0.0
    mean_cost_total = 0.0
    for count, values in zip(task_counts, task_stats, strict=True):
        attempts = values[0]
        if not count or not attempts:
            continue
        selected_tasks += count
        pass_rate_total += count * values[1] / attempts
        mean_cost_total += count * values[3] / attempts
    if not selected_tasks:
        return {
            "equal_task_pass_rate": None,
            "equal_task_mean_cost_per_attempt_usd": None,
            "equal_task_cpsc_usd": None,
        }
    pass_rate = pass_rate_total / selected_tasks
    mean_cost = mean_cost_total / selected_tasks
    return {
        "equal_task_pass_rate": pass_rate,
        "equal_task_mean_cost_per_attempt_usd": mean_cost,
        "equal_task_cpsc_usd": mean_cost / pass_rate if pass_rate else None,
    }


def _append_association_sample(
    samples: dict[str, list[float | None]],
    association: dict[str, object],
) -> None:
    for field in ("spearman", "kendall_tau_b"):
        value = association.get(field)
        samples[field].append(float(value) if value is not None else None)


def _association_interval(
    samples: dict[str, list[float | None]],
) -> dict[str, object]:
    summary: dict[str, object] = {}
    for field in ("spearman", "kendall_tau_b"):
        values = samples[field]
        low, high = _interval(values)
        summary[f"defined_{field}_replicates"] = sum(
            value is not None for value in values
        )
        summary[f"{field}_ci_low"] = low
        summary[f"{field}_ci_high"] = high
    return summary


def _delete_one_task_cpsc(
    matrix: dict[str, list[tuple[int, int, int, float, float, float]]],
    configs: list[str],
) -> dict[str, list[float | None]]:
    task_count = len(next(iter(matrix.values()), []))
    output: dict[str, list[float | None]] = {config: [] for config in configs}
    for omitted in range(task_count):
        counts = [1] * task_count
        counts[omitted] = 0
        for config in configs:
            output[config].append(
                _bootstrap_metrics(matrix[config], counts)["realized_cpsc_usd"]
            )
    return output


def _paired_cpsc_comparisons(
    configs: list[str],
    samples: dict[str, dict[str, list[float | None]]],
    *,
    point_cpsc: dict[str, float | None],
    jackknife_cpsc: dict[str, list[float | None]],
) -> list[dict[str, object]]:
    comparisons = []
    for index, config_a in enumerate(configs):
        for config_b in configs[index + 1 :]:
            paired = [
                (float(a), float(b))
                for a, b in zip(
                    samples[config_a]["realized_cpsc_usd"],
                    samples[config_b]["realized_cpsc_usd"],
                    strict=True,
                )
                if a is not None and b is not None and a > 0 and b > 0
            ]
            log_ratios = [log(a / b) for a, b in paired]
            low, high = _interval(log_ratios)
            defined = len(paired)
            pass_pairs = [
                (float(a), float(b))
                for a, b in zip(
                    samples[config_a]["pass_rate"],
                    samples[config_b]["pass_rate"],
                    strict=True,
                )
                if a is not None and b is not None
            ]
            pass_differences = [a - b for a, b in pass_pairs]
            pass_low, pass_high = _interval(pass_differences)
            a_cheaper = sum(a < b for a, b in paired)
            tied = sum(a == b for a, b in paired)
            a_higher_pass = sum(a > b for a, b in pass_pairs)
            point_a = point_cpsc[config_a]
            point_b = point_cpsc[config_b]
            point_log_ratio = (
                log(point_a / point_b)
                if point_a is not None
                and point_b is not None
                and point_a > 0
                and point_b > 0
                else None
            )
            jackknife_log_ratios = [
                log(float(a) / float(b))
                for a, b in zip(
                    jackknife_cpsc[config_a],
                    jackknife_cpsc[config_b],
                    strict=True,
                )
                if a is not None and b is not None and a > 0 and b > 0
            ]
            bca = _bca_interval(
                log_ratios,
                point_estimate=point_log_ratio,
                jackknife_estimates=jackknife_log_ratios,
            )
            comparisons.append(
                {
                    "config_a": config_a,
                    "config_b": config_b,
                    "defined_replicates": defined,
                    "log_cpsc_ratio_ci_low": low,
                    "log_cpsc_ratio_ci_high": high,
                    "point_log_cpsc_ratio": point_log_ratio,
                    "bca_log_cpsc_ratio_ci_low": bca["ci_low"],
                    "bca_log_cpsc_ratio_ci_high": bca["ci_high"],
                    "bca_bias_correction": bca["bias_correction"],
                    "bca_acceleration": bca["acceleration"],
                    "bca_defined_jackknife_clusters": len(jackknife_log_ratios),
                    "a_cheaper_replicates": a_cheaper,
                    "a_cheaper_bootstrap_share": (
                        a_cheaper / defined if defined else None
                    ),
                    "probability_a_cheaper": a_cheaper / defined if defined else None,
                    "tied_cpsc_replicates": tied,
                    "probability_tied": tied / defined if defined else None,
                    "defined_pass_rate_replicates": len(pass_pairs),
                    "pass_rate_difference_ci_low": pass_low,
                    "pass_rate_difference_ci_high": pass_high,
                    "a_higher_pass_rate_replicates": a_higher_pass,
                    "a_higher_pass_rate_bootstrap_share": (
                        a_higher_pass / len(pass_pairs) if pass_pairs else None
                    ),
                }
            )
    return comparisons


def _bca_interval(
    bootstrap_estimates: list[float],
    *,
    point_estimate: float | None,
    jackknife_estimates: list[float],
) -> dict[str, float | None]:
    if point_estimate is None or not bootstrap_estimates or not jackknife_estimates:
        return {
            "ci_low": None,
            "ci_high": None,
            "bias_correction": None,
            "acceleration": None,
        }
    sorted_bootstrap = sorted(bootstrap_estimates)
    less = sum(value < point_estimate for value in sorted_bootstrap)
    proportion = less / len(sorted_bootstrap)
    half_step = 0.5 / len(sorted_bootstrap)
    proportion = min(1.0 - half_step, max(half_step, proportion))
    normal = NormalDist()
    bias_correction = normal.inv_cdf(proportion)

    jackknife_mean = mean(jackknife_estimates)
    deviations = [jackknife_mean - value for value in jackknife_estimates]
    squared_sum = sum(value**2 for value in deviations)
    acceleration = (
        sum(value**3 for value in deviations) / (6 * squared_sum**1.5)
        if squared_sum
        else 0.0
    )

    adjusted_probabilities = []
    for probability in (0.025, 0.975):
        z_value = normal.inv_cdf(probability)
        numerator = bias_correction + z_value
        denominator = 1 - acceleration * numerator
        adjusted_z = (
            bias_correction + numerator / denominator
            if denominator
            else bias_correction + numerator
        )
        adjusted_probabilities.append(normal.cdf(adjusted_z))
    low_probability, high_probability = sorted(adjusted_probabilities)
    return {
        "ci_low": _percentile(sorted_bootstrap, low_probability),
        "ci_high": _percentile(sorted_bootstrap, high_probability),
        "bias_correction": bias_correction,
        "acceleration": acceleration,
    }


def _interval(values: list[float | None]) -> tuple[float | None, float | None]:
    finite = sorted(float(value) for value in values if value is not None)
    if not finite:
        return None, None
    return _percentile(finite, 0.025), _percentile(finite, 0.975)


def _percentile(sorted_values: list[float], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = probability * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + fraction * (
        sorted_values[upper] - sorted_values[lower]
    )


def _summarize_failure_charge_scenario(
    rows: list[dict[str, object]],
    *,
    base_budgets: dict[str, float],
    multiplier: float,
) -> list[dict[str, object]]:
    by_config: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_config[_required_str(row, "config")].append(row)

    summaries = []
    for config, config_rows in sorted(by_config.items()):
        successful = [row for row in config_rows if bool(row.get("passed"))]
        failed = [row for row in config_rows if not bool(row.get("passed"))]
        successes = len(successful)
        successful_cost = sum(float(row["_analysis_cost_usd"]) for row in successful)
        failure_charge = sum(
            multiplier * base_budgets[_required_str(row, "task_name")] for row in failed
        )
        total_charge = successful_cost + failure_charge
        cpsc = total_charge / successes if successes else None
        first = config_rows[0]
        summaries.append(
            {
                "config": config,
                "model": first.get("model"),
                "reasoning_effort": first.get("reasoning_effort"),
                "attempts": len(config_rows),
                "successes": successes,
                "failures": len(failed),
                "pass_rate": successes / len(config_rows) if config_rows else None,
                "total_proxy_failure_charge_usd": total_charge,
                "conditional_successful_spend_usd": (
                    successful_cost / successes if successes else None
                ),
                "proxy_failure_charge_reliability_tax_usd": (
                    failure_charge / successes if successes else None
                ),
                "proxy_failure_charge_reliability_tax_share": (
                    failure_charge / total_charge if total_charge else None
                ),
                "proxy_failure_charge_cpsc_usd": cpsc,
            }
        )
    return summaries


def _attach_ranks(rows: list[dict[str, object]]) -> None:
    pass_ranks = _average_ranks(rows, "pass_rate", reverse=True)
    cpsc_ranks = _average_ranks(rows, "realized_cpsc_usd", reverse=False)
    for row in rows:
        config = str(row["config"])
        pass_rank = pass_ranks.get(config)
        cpsc_rank = cpsc_ranks.get(config)
        row["pass_rate_rank"] = pass_rank
        row["realized_cpsc_rank"] = cpsc_rank
        row["rank_displacement"] = (
            cpsc_rank - pass_rank
            if pass_rank is not None and cpsc_rank is not None
            else None
        )


def _select_display_configurations(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_model: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_model[str(row.get("model") or row["config"])].append(row)
    selected = []
    for model_rows in by_model.values():
        selected.append(
            dict(
                min(
                    model_rows,
                    key=lambda row: (
                        -float(row.get("pass_rate") or 0.0),
                        float(
                            row.get("mean_cost_per_attempt_usd") or float("inf")
                        ),
                        str(row["config"]),
                    ),
                )
            )
        )
    return sorted(
        selected,
        key=lambda row: (
            -float(row.get("pass_rate") or 0.0),
            str(row["config"]),
        ),
    )


def _rank_association(rows: list[dict[str, object]]) -> dict[str, float | int | None]:
    paired = [
        (float(row["pass_rate_rank"]), float(row["realized_cpsc_rank"]))
        for row in rows
        if row.get("pass_rate_rank") is not None
        and row.get("realized_cpsc_rank") is not None
    ]
    if len(paired) < 2:
        return {"configurations": len(paired), "spearman": None, "kendall_tau_b": None}
    x_values = [pair[0] for pair in paired]
    y_values = [pair[1] for pair in paired]
    x_mean = mean(x_values)
    y_mean = mean(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in paired)
    x_scale = sum((x - x_mean) ** 2 for x in x_values)
    y_scale = sum((y - y_mean) ** 2 for y in y_values)
    spearman = numerator / sqrt(x_scale * y_scale) if x_scale and y_scale else None

    concordant = 0
    discordant = 0
    ties_x = 0
    ties_y = 0
    for index, (x_a, y_a) in enumerate(paired):
        for x_b, y_b in paired[index + 1 :]:
            x_delta = x_a - x_b
            y_delta = y_a - y_b
            if x_delta == 0 and y_delta == 0:
                continue
            if x_delta == 0:
                ties_x += 1
            elif y_delta == 0:
                ties_y += 1
            elif x_delta * y_delta > 0:
                concordant += 1
            else:
                discordant += 1
    kendall_denominator = sqrt(
        (concordant + discordant + ties_x)
        * (concordant + discordant + ties_y)
    )
    kendall = (
        (concordant - discordant) / kendall_denominator
        if kendall_denominator
        else None
    )
    return {
        "configurations": len(paired),
        "spearman": spearman,
        "kendall_tau_b": kendall,
    }


def _effort_rank_association(rows: list[dict[str, object]]) -> dict[str, object]:
    by_model: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_model[str(row.get("model") or row["config"])].append(row)

    pooled_rows = []
    by_model_results = []
    for model, model_rows in sorted(by_model.items()):
        if len(model_rows) < 2:
            continue
        ranked_rows = [dict(row) for row in model_rows]
        _attach_ranks(ranked_rows)
        association = _rank_association(ranked_rows)
        by_model_results.append({"model": model, **association})
        pooled_rows.extend(ranked_rows)
    pooled = _rank_association(pooled_rows)
    return {
        "status": "descriptive_within_model_effort_decomposition",
        "pooled_within_model": {
            "models": len(by_model_results),
            **pooled,
        },
        "by_model": by_model_results,
    }


def _attach_attempt_cost_frontier(rows: list[dict[str, object]]) -> None:
    for candidate in rows:
        candidate_pass_rate = candidate.get("pass_rate")
        candidate_cost = candidate.get("mean_cost_per_attempt_usd")
        if candidate_pass_rate is None or candidate_cost is None:
            candidate["attempt_cost_pareto_frontier"] = False
            continue
        candidate["attempt_cost_pareto_frontier"] = not any(
            _dominates(
                other,
                pass_rate=float(candidate_pass_rate),
                attempt_cost=float(candidate_cost),
            )
            for other in rows
            if other is not candidate
        )


def _dominates(
    row: dict[str, object],
    *,
    pass_rate: float,
    attempt_cost: float,
) -> bool:
    other_pass_rate = row.get("pass_rate")
    other_cost = row.get("mean_cost_per_attempt_usd")
    if other_pass_rate is None or other_cost is None:
        return False
    other_pass_rate = float(other_pass_rate)
    other_cost = float(other_cost)
    return (
        other_pass_rate >= pass_rate
        and other_cost <= attempt_cost
        and (other_pass_rate > pass_rate or other_cost < attempt_cost)
    )


def _reliability_floor_curve(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    curve = []
    for floor in DEFAULT_RELIABILITY_FLOORS:
        eligible = [
            row
            for row in rows
            if row.get("pass_rate") is not None
            and float(row["pass_rate"]) >= floor
            and row.get("realized_cpsc_usd") is not None
        ]
        best = min(
            eligible,
            key=lambda row: (float(row["realized_cpsc_usd"]), str(row["config"])),
            default=None,
        )
        curve.append(
            {
                "minimum_pass_rate": floor,
                "eligible_configurations": len(eligible),
                "minimum_cpsc_config": best.get("config") if best else None,
                "minimum_cpsc_usd": best.get("realized_cpsc_usd") if best else None,
                "observed_pass_rate": best.get("pass_rate") if best else None,
            }
        )
    return curve


def _average_ranks(
    rows: list[dict[str, object]],
    field: str,
    *,
    reverse: bool,
) -> dict[str, float]:
    ranked = [row for row in rows if row.get(field) is not None]
    ranked.sort(
        key=lambda row: (
            -float(row[field]) if reverse else float(row[field]),
            str(row["config"]),
        )
    )
    ranks: dict[str, float] = {}
    cursor = 0
    while cursor < len(ranked):
        end = cursor + 1
        value = float(ranked[cursor][field])
        while end < len(ranked) and float(ranked[end][field]) == value:
            end += 1
        average_rank = ((cursor + 1) + end) / 2
        for row in ranked[cursor:end]:
            ranks[str(row["config"])] = average_rank
        cursor = end
    return ranks


def _required_str(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"DeepSWE trial row missing {field}")
    return value


def _planned_artifact(plan: dict[str, Any], artifact_id: str) -> dict[str, object]:
    artifacts = plan.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("DeepSWE economics plan missing artifacts list")
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("id") == artifact_id:
            return artifact
    raise ValueError(f"DeepSWE economics plan missing artifact: {artifact_id}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build the versioned DeepSWE v1.1 CPSC analysis report",
    )
    parser.add_argument("trials_json", type=Path)
    parser.add_argument("leaderboard_json", type=Path)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("configs/deepswe-cpsc-v0.2.json"),
    )
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        help="override only for development smoke tests; paper output uses the frozen plan",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the report to this path instead of standard output",
    )
    args = parser.parse_args(argv)

    plan = json.loads(args.plan.read_text())
    trials_spec = _planned_artifact(plan, "trials")
    leaderboard_spec = _planned_artifact(plan, "leaderboard")
    verification = {
        "trials": verify_artifact(
            args.trials_json,
            expected_bytes=int(trials_spec["bytes"]),
            expected_sha256=str(trials_spec["sha256"]),
        ),
        "leaderboard": verify_artifact(
            args.leaderboard_json,
            expected_bytes=int(leaderboard_spec["bytes"]),
            expected_sha256=str(leaderboard_spec["sha256"]),
        ),
    }
    report = build_deepswe_economics_report(
        json.loads(args.trials_json.read_text()),
        json.loads(args.leaderboard_json.read_text()),
        plan,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    report["artifact_verification"] = verification
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

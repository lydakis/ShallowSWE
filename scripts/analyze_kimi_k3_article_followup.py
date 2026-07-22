#!/usr/bin/env python3
"""Run the reproducible existing-data follow-up for the Kimi K3 article."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from typing import Any

try:
    from scripts.kimi_k3_analysis_core import (
        interval,
        lineage_correlations,
        mean,
        pearson,
        rankdata,
        reported_cost,
        reprice_k3,
        residualize,
        spend_decomposition,
        summarize_cache_rows,
        summarize_retry_task,
    )
except ModuleNotFoundError:
    from kimi_k3_analysis_core import (  # type: ignore[no-redef]
        interval,
        lineage_correlations,
        mean,
        pearson,
        rankdata,
        reported_cost,
        reprice_k3,
        residualize,
        spend_decomposition,
        summarize_cache_rows,
        summarize_retry_task,
    )


SCHEMA_VERSION = "shallowswe.kimi_k3_article_followup.v0.1"
LABELS = {
    "G": "Grok 4.5 high",
    "S": "GPT-5.6 Sol high",
    "X": "GPT-5.6 Sol xhigh",
    "M": "GPT-5.6 Sol max",
    "T": "GPT-5.6 Terra max",
    "L": "GPT-5.6 Luna max",
    "K": "Kimi K3 max",
    "F": "Claude Fable 5 xhigh",
    "K2": "Kimi K2.7 Code default",
}
FOCAL = ("G", "S", "X", "M", "T", "L", "K", "F")
__all__ = [
    "pearson",
    "rankdata",
    "residualize",
    "spend_decomposition",
    "summarize_cache_rows",
    "summarize_retry_task",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", required=True, type=Path)
    parser.add_argument("--tasks", required=True, type=Path)
    parser.add_argument("--cache-results", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap-replicates", type=int)
    parser.add_argument("--seed", type=int)
    return parser.parse_args(argv)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_source(path: Path, expected: str) -> dict[str, Any]:
    observed = file_sha256(path)
    if observed != expected:
        raise ValueError(f"source hash mismatch for {path}: {observed} != {expected}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": observed}


def prepare_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    scored = [
        dict(row)
        for row in rows
        if row.get("source") == "deep-swe" and row.get("included_in_score") is True
    ]
    observed: dict[str, list[float]] = defaultdict(list)
    for row in scored:
        if row.get("cost_usd") is not None:
            observed[str(row["config"])].append(float(row["cost_usd"]))
    for row in scored:
        config = str(row["config"])
        if row.get("cost_usd") is None:
            if not observed[config]:
                raise ValueError(f"configuration {config} has no observed costs")
            row["_analysis_cost_usd"] = mean(observed[config])
            row["_cost_imputed"] = True
        else:
            row["_analysis_cost_usd"] = float(row["cost_usd"])
            row["_cost_imputed"] = False
    return scored


def group_attempts(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, list[Mapping[str, Any]]]]:
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row["config"])][str(row["task_name"])].append(row)
    return grouped


def complete_tasks(
    attempts: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    configs: Sequence[str],
) -> list[str]:
    candidates = set(attempts[configs[0]])
    for config in configs[1:]:
        candidates &= set(attempts[config])
    return sorted(
        task for task in candidates if all(len(attempts[config][task]) == 4 for config in configs)
    )


def task_rate(rows: Sequence[Mapping[str, Any]]) -> float:
    return sum(bool(row.get("passed")) for row in rows) / len(rows)


def repository_groups(tasks: Sequence[str], repositories: Mapping[str, str]) -> list[list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, task in enumerate(tasks):
        groups[repositories[task]].append(index)
    return [groups[repository] for repository in sorted(groups)]


def sampled_indices(groups: Sequence[Sequence[int]], rng: random.Random) -> list[int]:
    return [index for _ in groups for index in groups[rng.randrange(len(groups))]]


def broad_controls(
    attempts: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    tasks: Sequence[str],
    excluded: set[str],
) -> list[str]:
    return sorted(
        config
        for config, task_rows in attempts.items()
        if config not in excluded
        and all(task in task_rows and len(task_rows[task]) == 4 for task in tasks)
    )


def lineage_analysis(
    attempts: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    symbol_configs: Mapping[str, str],
    repositories: Mapping[str, str],
    spec: Mapping[str, Any],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    pair_symbols = list(spec["lineage"]["pair_complete_cohort"])
    focal_symbols = list(spec["lineage"]["focal_complete_cohort"])
    cohorts = {
        "pair_complete": complete_tasks(attempts, [symbol_configs[s] for s in pair_symbols]),
        "focal_complete": complete_tasks(attempts, [symbol_configs[s] for s in focal_symbols]),
    }
    variants: list[dict[str, Any]] = []
    control_lists: dict[str, dict[str, list[str]]] = {}
    for cohort_name, tasks in cohorts.items():
        broad = broad_controls(
            attempts,
            tasks,
            {symbol_configs[symbol] for symbol in ("K", "K2", "F")},
        )
        controls: dict[str, list[str]] = {"none": [], "broad_complete": broad}
        if cohort_name == "focal_complete":
            controls["focal_shared"] = [
                symbol_configs[symbol] for symbol in spec["lineage"]["focal_shared_control"]
            ]
        control_lists[cohort_name] = controls
        rates = {
            symbol: [task_rate(attempts[symbol_configs[symbol]][task]) for task in tasks]
            for symbol in ("K", "K2", "F")
        }
        groups = repository_groups(tasks, repositories)
        for control_name, control_configs in controls.items():
            control = (
                [
                    mean([task_rate(attempts[config][task]) for config in control_configs])
                    for task in tasks
                ]
                if control_configs
                else None
            )
            for transform in ("raw", "empirical_logit", "rank"):
                values = lineage_correlations(
                    rates["K"],
                    rates["K2"],
                    rates["F"],
                    control=control,
                    transform=transform,
                    pseudocount=float(spec["lineage"]["empirical_logit_pseudocount"]),
                )
                samples = {field: [] for field in values}
                rng = random.Random(seed + len(variants) * 1009)
                for _ in range(replicates):
                    indices = sampled_indices(groups, rng)
                    sampled = {
                        symbol: [rates[symbol][index] for index in indices] for symbol in rates
                    }
                    sampled_control = (
                        [control[index] for index in indices] if control is not None else None
                    )
                    result = lineage_correlations(
                        sampled["K"],
                        sampled["K2"],
                        sampled["F"],
                        control=sampled_control,
                        transform=transform,
                        pseudocount=float(spec["lineage"]["empirical_logit_pseudocount"]),
                    )
                    for field, value in result.items():
                        if math.isfinite(value):
                            samples[field].append(value)
                variant_id = f"{cohort_name}_{transform}_{control_name}"
                variants.append(
                    {
                        "id": variant_id,
                        "cohort": cohort_name,
                        "tasks": len(tasks),
                        "repositories": len(groups),
                        "transform": transform,
                        "control": control_name,
                        "control_configurations": control_configs,
                        **values,
                        **{f"{field}_ci": interval(sample) for field, sample in samples.items()},
                    }
                )
    primary_id = str(spec["lineage"]["primary_variant"])
    primary = next(row for row in variants if row["id"] == primary_id)
    pair_tasks = cohorts["pair_complete"]
    any_solve = {
        task: {
            symbol: any(row.get("passed") for row in attempts[symbol_configs[symbol]][task])
            for symbol in ("K", "K2")
        }
        for task in pair_tasks
    }
    return {
        "cohorts": {name: len(tasks) for name, tasks in cohorts.items()},
        "control_configurations": control_lists,
        "primary_variant": primary,
        "variants": variants,
        "pair_complete_observed": {
            "k2_pass_rate": mean(
                [task_rate(attempts[symbol_configs["K2"]][task]) for task in pair_tasks]
            ),
            "k3_pass_rate": mean(
                [task_rate(attempts[symbol_configs["K"]][task]) for task in pair_tasks]
            ),
            "both_any_solve": sum(v["K"] and v["K2"] for v in any_solve.values()),
            "k2_only_any_solve": sum(v["K2"] and not v["K"] for v in any_solve.values()),
            "k3_only_any_solve": sum(v["K"] and not v["K2"] for v in any_solve.values()),
            "neither_any_solve": sum(not v["K"] and not v["K2"] for v in any_solve.values()),
        },
    }


def aggregate_retry(rows: Sequence[Mapping[str, float]]) -> dict[str, float]:
    coverage = mean([float(row["coverage"]) for row in rows])
    cost = mean([float(row["stopped_cost_usd"]) for row in rows])
    return {
        "coverage": coverage,
        "stopped_cost_per_task_usd": cost,
        "stopped_cpsc_usd": cost / coverage,
    }


def retry_analysis(
    attempts: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    symbol_configs: Mapping[str, str],
    tasks: Sequence[str],
    repositories: Mapping[str, str],
    symbols: Sequence[str],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    task_rows = {
        symbol: {
            attempt_count: {
                task: summarize_retry_task(
                    attempts[symbol_configs[symbol]][task], attempts=attempt_count
                )
                for task in tasks
            }
            for attempt_count in range(1, 5)
        }
        for symbol in symbols
    }
    groups = repository_groups(tasks, repositories)
    samples = {
        symbol: {
            attempt_count: {field: [] for field in ("coverage", "cost", "cpsc")}
            for attempt_count in range(1, 5)
        }
        for symbol in symbols
    }
    replicate_points: list[dict[str, dict[int, dict[str, float]]]] = []
    rng = random.Random(seed + 91_003)
    for _ in range(replicates):
        indices = sampled_indices(groups, rng)
        replicate: dict[str, dict[int, dict[str, float]]] = defaultdict(dict)
        for symbol in symbols:
            for attempt_count in range(1, 5):
                point = aggregate_retry(
                    [task_rows[symbol][attempt_count][tasks[index]] for index in indices]
                )
                replicate[symbol][attempt_count] = point
                samples[symbol][attempt_count]["coverage"].append(point["coverage"])
                samples[symbol][attempt_count]["cost"].append(point["stopped_cost_per_task_usd"])
                samples[symbol][attempt_count]["cpsc"].append(point["stopped_cpsc_usd"])
        replicate_points.append(replicate)
    models: dict[str, Any] = {}
    for symbol in symbols:
        curve = []
        for attempt_count in range(1, 5):
            point = aggregate_retry(list(task_rows[symbol][attempt_count].values()))
            curve.append(
                {
                    "attempts": attempt_count,
                    **point,
                    "coverage_ci": interval(samples[symbol][attempt_count]["coverage"]),
                    "stopped_cost_per_task_usd_ci": interval(
                        samples[symbol][attempt_count]["cost"]
                    ),
                    "stopped_cpsc_usd_ci": interval(samples[symbol][attempt_count]["cpsc"]),
                }
            )
        models[symbol] = {"label": LABELS[symbol], "curve": curve}
    contrasts = []
    for comparator in [symbol for symbol in symbols if symbol != "K"]:
        for attempt_count in range(1, 5):
            k3 = models["K"]["curve"][attempt_count - 1]
            other = models[comparator]["curve"][attempt_count - 1]
            contrast_samples = {
                "coverage": [
                    row["K"][attempt_count]["coverage"] - row[comparator][attempt_count]["coverage"]
                    for row in replicate_points
                ],
                "cost": [
                    row["K"][attempt_count]["stopped_cost_per_task_usd"]
                    - row[comparator][attempt_count]["stopped_cost_per_task_usd"]
                    for row in replicate_points
                ],
                "cpsc": [
                    row["K"][attempt_count]["stopped_cpsc_usd"]
                    - row[comparator][attempt_count]["stopped_cpsc_usd"]
                    for row in replicate_points
                ],
            }
            contrasts.append(
                {
                    "comparator": comparator,
                    "attempts": attempt_count,
                    "coverage_difference": k3["coverage"] - other["coverage"],
                    "coverage_difference_ci": interval(contrast_samples["coverage"]),
                    "stopped_cost_difference_usd": (
                        k3["stopped_cost_per_task_usd"] - other["stopped_cost_per_task_usd"]
                    ),
                    "stopped_cost_difference_usd_ci": interval(contrast_samples["cost"]),
                    "stopped_cpsc_difference_usd": (
                        k3["stopped_cpsc_usd"] - other["stopped_cpsc_usd"]
                    ),
                    "stopped_cpsc_difference_usd_ci": interval(contrast_samples["cpsc"]),
                }
            )
    dominance = []
    for k3_attempts in range(1, 5):
        for other_attempts in range(1, 5):
            k3 = models["K"]["curve"][k3_attempts - 1]
            luna = models["L"]["curve"][other_attempts - 1]
            probability = mean(
                [
                    float(
                        row["L"][other_attempts]["coverage"] >= row["K"][k3_attempts]["coverage"]
                        and row["L"][other_attempts]["stopped_cost_per_task_usd"]
                        <= row["K"][k3_attempts]["stopped_cost_per_task_usd"]
                    )
                    for row in replicate_points
                ]
            )
            dominance.append(
                {
                    "k3_attempts": k3_attempts,
                    "luna_attempts": other_attempts,
                    "point_dominates": (
                        luna["coverage"] >= k3["coverage"]
                        and luna["stopped_cost_per_task_usd"] <= k3["stopped_cost_per_task_usd"]
                    ),
                    "bootstrap_dominance_probability": probability,
                }
            )
    return {"models": models, "same_attempt_contrasts": contrasts, "luna_dominance": dominance}


def standalone_analysis(
    attempts: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    symbol_configs: Mapping[str, str],
    tasks: Sequence[str],
    repositories: Mapping[str, str],
    prices: Mapping[str, float],
    cache_fractions: Sequence[float],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    groups = repository_groups(tasks, repositories)
    models: dict[str, Any] = {}
    for symbol in FOCAL:
        rows = [row for task in tasks for row in attempts[symbol_configs[symbol]][task]]
        successes = sum(bool(row.get("passed")) for row in rows)
        pass_samples = []
        cpsc_samples = []
        rng = random.Random(seed + 700 + FOCAL.index(symbol))
        for _ in range(replicates):
            indices = sampled_indices(groups, rng)
            sampled_rows = [
                row for index in indices for row in attempts[symbol_configs[symbol]][tasks[index]]
            ]
            sampled_successes = sum(bool(row.get("passed")) for row in sampled_rows)
            pass_samples.append(sampled_successes / len(sampled_rows))
            if sampled_successes:
                cpsc_samples.append(
                    sum(reported_cost(row) for row in sampled_rows) / sampled_successes
                )
        models[symbol] = {
            "label": LABELS[symbol],
            "attempts": len(rows),
            "successes": successes,
            "imputed_cost_rows": sum(bool(row.get("_cost_imputed")) for row in rows),
            "pass_rate": successes / len(rows),
            "pass_rate_ci": interval(pass_samples),
            "realized_cpsc_usd": sum(reported_cost(row) for row in rows) / successes,
            "realized_cpsc_usd_ci": interval(cpsc_samples),
        }
    k3_rows = [row for task in tasks for row in attempts[symbol_configs["K"]][task]]
    k3_successes = sum(bool(row.get("passed")) for row in k3_rows)
    sensitivity = [
        {
            "cache_fraction": fraction,
            "realized_cpsc_usd": sum(reprice_k3(row, fraction, prices) for row in k3_rows)
            / k3_successes,
        }
        for fraction in cache_fractions
    ]
    return {"models": models, "k3_cache_sensitivity": sensitivity}


def decomposition_analysis(
    attempts: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    symbol_configs: Mapping[str, str],
    tasks: Sequence[str],
    repositories: Mapping[str, str],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    symbols = ("K", "S", "L", "F")
    pooled = {}
    task_conditioned = {}
    for symbol in symbols:
        rows = [row for task in tasks for row in attempts[symbol_configs[symbol]][task]]
        pooled[symbol] = {"label": LABELS[symbol], **spend_decomposition(rows)}
        defined = []
        for task in tasks:
            task_rows = attempts[symbol_configs[symbol]][task]
            if any(row.get("passed") for row in task_rows):
                defined.append(spend_decomposition(task_rows))
        task_conditioned[symbol] = {
            "label": LABELS[symbol],
            "defined_tasks": len(defined),
            "all_fail_tasks": len(tasks) - len(defined),
            "mean_success_cost_usd": mean([float(row["mean_success_cost_usd"]) for row in defined]),
            "mean_realized_reliability_tax_usd": mean(
                [float(row["realized_reliability_tax_usd"]) for row in defined]
            ),
            "mean_realized_cpsc_usd": mean([float(row["realized_cpsc_usd"]) for row in defined]),
        }
    groups = repository_groups(tasks, repositories)
    samples = {
        symbol: {field: [] for field in ("gap", "success", "tax", "share")} for symbol in ("S", "L")
    }
    rng = random.Random(seed + 190_001)
    for _ in range(replicates):
        indices = sampled_indices(groups, rng)
        results = {}
        for symbol in ("K", "S", "L"):
            rows = [
                row for index in indices for row in attempts[symbol_configs[symbol]][tasks[index]]
            ]
            results[symbol] = spend_decomposition(rows)
        for comparator in ("S", "L"):
            gap = float(results["K"]["realized_cpsc_usd"]) - float(
                results[comparator]["realized_cpsc_usd"]
            )
            success_gap = float(results["K"]["mean_success_cost_usd"]) - float(
                results[comparator]["mean_success_cost_usd"]
            )
            tax_gap = float(results["K"]["realized_reliability_tax_usd"]) - float(
                results[comparator]["realized_reliability_tax_usd"]
            )
            samples[comparator]["gap"].append(gap)
            samples[comparator]["success"].append(success_gap)
            samples[comparator]["tax"].append(tax_gap)
            if gap > 0:
                samples[comparator]["share"].append(success_gap / gap)
    contrasts = {}
    for comparator in ("S", "L"):
        gap = float(pooled["K"]["realized_cpsc_usd"]) - float(
            pooled[comparator]["realized_cpsc_usd"]
        )
        success_gap = float(pooled["K"]["mean_success_cost_usd"]) - float(
            pooled[comparator]["mean_success_cost_usd"]
        )
        tax_gap = float(pooled["K"]["realized_reliability_tax_usd"]) - float(
            pooled[comparator]["realized_reliability_tax_usd"]
        )
        contrasts[f"K_minus_{comparator}"] = {
            "cpsc_gap_usd": gap,
            "cpsc_gap_usd_ci": interval(samples[comparator]["gap"]),
            "successful_spend_gap_usd": success_gap,
            "successful_spend_gap_usd_ci": interval(samples[comparator]["success"]),
            "reliability_tax_gap_usd": tax_gap,
            "reliability_tax_gap_usd_ci": interval(samples[comparator]["tax"]),
            "successful_spend_share_of_positive_gap": success_gap / gap,
            "successful_spend_share_of_positive_gap_ci": interval(samples[comparator]["share"]),
        }
    return {
        "pooled": pooled,
        "task_conditioned_sensitivity": task_conditioned,
        "contrasts": contrasts,
    }


def cache_analysis(
    rows: Sequence[Mapping[str, Any]],
    bins: Sequence[tuple[int, int | None]],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    point = summarize_cache_rows(rows, bins)
    by_task: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[str(row["task_id"])].append(row)
    task_ids = sorted(by_task)
    overall_samples = []
    bin_samples = [[] for _ in bins]
    rng = random.Random(seed + 270_011)
    for _ in range(replicates):
        sampled = [row for _ in task_ids for row in by_task[task_ids[rng.randrange(len(task_ids))]]]
        result = summarize_cache_rows(sampled, bins)
        overall_samples.append(float(result["token_weighted_cache_share"]))
        for index, row in enumerate(result["step_bins"]):
            value = float(row["token_weighted_cache_share"])
            if math.isfinite(value):
                bin_samples[index].append(value)
    point["token_weighted_cache_share_ci"] = interval(overall_samples)
    for index, row in enumerate(point["step_bins"]):
        row["token_weighted_cache_share_ci"] = interval(bin_samples[index])
        row["defined_bootstrap_replicates"] = len(bin_samples[index])
    return point


def clean_json(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    spec = load_json(args.spec)
    controls = spec["analysis_controls"]
    replicates = args.bootstrap_replicates or int(controls["bootstrap_replicates"])
    seed = args.seed or int(controls["seed"])
    source_spec = spec["sources"]
    verified = {
        "trials": verify_source(args.trials, source_spec["deepswe_trials"]["sha256"]),
        "tasks": verify_source(args.tasks, source_spec["deepswe_tasks"]["sha256"]),
        "cache_results": verify_source(
            args.cache_results, source_spec["shallowswe_k3_repair_loops"]["sha256"]
        ),
    }
    raw_trials = load_json(args.trials)["rows"]
    task_rows = load_json(args.tasks)["rows"]
    cache_rows = load_json(args.cache_results)
    rows = prepare_rows(raw_trials)
    attempts = group_attempts(rows)
    symbol_configs = {str(key): str(value) for key, value in spec["configs"].items()}
    repositories = {str(row["id"]): str(row["repository"]) for row in task_rows}
    focal_tasks = complete_tasks(attempts, [symbol_configs[symbol] for symbol in (*FOCAL, "K2")])
    prices = spec["cache"]["prices_usd_per_million"]
    bins = [
        (int(lower), int(upper) if upper is not None else None)
        for lower, upper in spec["cache"]["step_bins"]
    ]
    output = {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": spec["analysis_id"],
        "scope": "existing public DeepSWE rows plus 54 pre-existing ShallowSWE K3 trajectories; no new model outcomes",
        "artifact_verification": verified,
        "analysis_controls": {"bootstrap_replicates": replicates, "seed": seed},
        "data_quality": {
            "deep_swe_source_rows": len(raw_trials),
            "deep_swe_scored_rows": len(rows),
            "deep_swe_duplicate_scored_trial_names": len(rows)
            - len({str(row["trial_name"]) for row in rows}),
            "imputed_cost_rows": sum(bool(row["_cost_imputed"]) for row in rows),
            "imputed_cost_rows_by_configuration": {
                config: sum(
                    bool(row["_cost_imputed"]) for row in rows if str(row["config"]) == config
                )
                for config in sorted(
                    {str(row["config"]) for row in rows if bool(row["_cost_imputed"])}
                )
            },
            "task_index_rows": len(task_rows),
            "cache_rows": len(cache_rows),
            "cache_duplicate_run_ids": len(cache_rows)
            - len({str(row["run_id"]) for row in cache_rows}),
            "cache_missing_core_counters": sum(
                any(
                    row.get(field) is None
                    for field in ("input_tokens", "cache_read_tokens", "agent_steps")
                )
                for row in cache_rows
            ),
        },
        "cohort": {
            "matched_frontier_tasks": len(focal_tasks),
            "matched_frontier_repositories": len({repositories[task] for task in focal_tasks}),
            "attempts_per_configuration_task": 4,
        },
    }
    output["lineage"] = lineage_analysis(
        attempts, symbol_configs, repositories, spec, replicates, seed
    )
    output["retry"] = retry_analysis(
        attempts,
        symbol_configs,
        focal_tasks,
        repositories,
        spec["retry"]["symbols"],
        replicates,
        seed,
    )
    output["standalone"] = standalone_analysis(
        attempts,
        symbol_configs,
        focal_tasks,
        repositories,
        prices,
        spec["cache"]["deep_swe_sensitivity_fractions"],
        replicates,
        seed,
    )
    output["decomposition"] = decomposition_analysis(
        attempts, symbol_configs, focal_tasks, repositories, replicates, seed
    )
    output["cache_amortization"] = cache_analysis(cache_rows, bins, replicates, seed)
    return clean_json(output)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reproduce the frozen retrospective DeepSWE Kimi K3 discovery analysis.

The script evaluates the retrospective policies and source snapshot declared by a protocol JSON.
It keeps multiset coverage, left-to-right stopped cost, task/repository uncertainty, and K3
cache-accounting sensitivity in one inspectable path. The protocol's former run design is
superseded; this analyzer makes no prospective or confirmatory claim.

Example:

  uv run python scripts/analyze_kimi_k3_frontier_followup.py \
    --trials /path/to/deepswe-v1.1-trials.json \
    --tasks /path/to/deepswe-v1.1-tasks.json \
    --protocol configs/analyses/kimi-k3-frontier-retrospective-2026-07-19/spec.json \
    --output /tmp/kimi-k3-frontier-followup.json
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import stdev
from typing import Any


SCHEMA_VERSION = "shallowswe.kimi_k3_frontier_followup_analysis.v0.1"
PRIMARY_POLICY_IDS = ("P0", "P1", "P2", "P3", "A0")
DEFAULT_BOOTSTRAP_REPLICATES = 10_000
DEFAULT_SEED = 20_260_719

Trial = dict[str, Any]
TaskPolicySummary = dict[str, float]
CostFunction = Callable[[str, Trial], float]


def configured_cache_fractions(protocol: Mapping[str, Any]) -> tuple[float, ...]:
    """Return the frozen fallback grid plus explicitly labeled research sensitivities."""
    cache_plan = _required_object(protocol, "cache_accounting")
    fractions: list[float] = []
    for field in ("fallback_cache_fractions", "supplemental_research_cache_fractions"):
        values = _required_list(cache_plan, field)
        for value in values:
            fraction = float(value)
            if not 0.0 <= fraction <= 1.0:
                raise ValueError(f"{field} contains an invalid cache fraction: {fraction}")
            fractions.append(fraction)
    return tuple(sorted(set(fractions)))


def bootstrap_seeds(seed: int) -> dict[str, int]:
    """Use the exact same frozen seed for both declared bootstrap analyses."""
    return {"task_cluster": seed, "repository_cluster": seed}


def linear_break_even_fraction(value_at_zero: float, value_at_one: float) -> dict[str, Any]:
    """Solve a cache-linear contrast for zero and state whether the root is feasible."""
    slope = value_at_one - value_at_zero
    fraction = -value_at_zero / slope if slope else None
    return {
        "cache_fraction": fraction,
        "feasible": fraction is not None and 0.0 <= fraction <= 1.0,
        "value_at_zero": value_at_zero,
        "value_at_one": value_at_one,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trials", required=True, type=Path, help="DeepSWE trials JSON")
    parser.add_argument("--tasks", required=True, type=Path, help="DeepSWE tasks JSON")
    parser.add_argument("--protocol", required=True, type=Path, help="frozen protocol JSON")
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout")
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=DEFAULT_BOOTSTRAP_REPLICATES,
        help="paired task/repository bootstrap replicates",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="bootstrap seed")
    return parser.parse_args(argv)


def enumerate_policy_sequences(
    policy: Sequence[str],
    attempts_by_symbol: Mapping[str, Sequence[Trial]],
) -> Iterator[tuple[tuple[str, Trial], ...]]:
    """Yield every distinct assignment of attempts to an ordered model-symbol multiset."""
    pools = {
        symbol: tuple(sorted(attempts_by_symbol[symbol], key=lambda row: str(row["trial_name"])))
        for symbol in set(policy)
    }

    def visit(
        position: int,
        chosen: tuple[tuple[str, Trial], ...],
        used_indices: dict[str, frozenset[int]],
    ) -> Iterator[tuple[tuple[str, Trial], ...]]:
        if position == len(policy):
            yield chosen
            return
        symbol = policy[position]
        if symbol not in pools:
            raise ValueError(f"policy symbol {symbol} has no attempts")
        used = used_indices.get(symbol, frozenset())
        for index, row in enumerate(pools[symbol]):
            if index in used:
                continue
            next_used = dict(used_indices)
            next_used[symbol] = used | {index}
            yield from visit(position + 1, (*chosen, (symbol, row)), next_used)

    yield from visit(0, (), {})


def reported_cost(row: Trial) -> float:
    value = row.get("_analysis_cost_usd", row.get("cost_usd"))
    if value is None:
        raise ValueError(f"trial {row.get('trial_name')} lacks reported or imputed cost")
    return float(value)


def k3_repriced_cost(
    row: Trial,
    *,
    cache_fraction: float,
    uncached_input_per_1m: float = 3.0,
    cached_input_per_1m: float = 0.3,
    output_per_1m: float = 15.0,
) -> float:
    """Reprice a K3 row without treating the historical 98% cache assumption as observed."""
    if not 0.0 <= cache_fraction <= 1.0:
        raise ValueError("cache_fraction must be between zero and one")
    input_tokens = int(row.get("n_input_tokens") or 0)
    output_tokens = int(row.get("n_output_tokens") or 0)
    effective_input_rate = (
        uncached_input_per_1m * (1.0 - cache_fraction) + cached_input_per_1m * cache_fraction
    )
    return (input_tokens * effective_input_rate + output_tokens * output_per_1m) / 1_000_000


def summarize_task_policy(
    policy: Sequence[str],
    attempts_by_symbol: Mapping[str, Sequence[Trial]],
    *,
    cache_fraction: float | None = None,
    k3_prices: Mapping[str, float] | None = None,
) -> TaskPolicySummary:
    """Average stopped-policy outcomes over every within-task attempt assignment."""
    sequences = list(enumerate_policy_sequences(policy, attempts_by_symbol))
    if not sequences:
        raise ValueError(f"policy {''.join(policy)} has no valid attempt assignments")
    prices = dict(k3_prices or {})
    totals = defaultdict(float)
    for sequence in sequences:
        success = False
        exact_agent_timeout = False
        for symbol, row in sequence:
            totals["attempts"] += 1
            if symbol == "K" and cache_fraction is not None:
                totals["cost"] += k3_repriced_cost(
                    row,
                    cache_fraction=cache_fraction,
                    uncached_input_per_1m=float(prices.get("uncached_input", 3.0)),
                    cached_input_per_1m=float(prices.get("cached_input", 0.3)),
                    output_per_1m=float(prices.get("output", 15.0)),
                )
            else:
                totals["cost"] += reported_cost(row)
            totals["agent_steps"] += float(row.get("n_agent_steps") or 0)
            totals["input_tokens"] += float(row.get("n_input_tokens") or 0)
            totals["cache_tokens"] += float(row.get("n_cache_tokens") or 0)
            totals["output_tokens"] += float(row.get("n_output_tokens") or 0)
            totals["agent_seconds"] += float(row.get("agent_duration_seconds") or 0)
            totals["trial_seconds"] += float(row.get("trial_duration_seconds") or 0)
            exact_agent_timeout = exact_agent_timeout or (
                row.get("error_category") == "agent_timeout"
                and abs(float(row.get("agent_duration_seconds") or 0) - 10_800.0) <= 1.0
            )
            if bool(row.get("passed")):
                success = True
                break
        totals["coverage"] += float(success)
        totals["exact_agent_timeout"] += float(exact_agent_timeout)

    denominator = len(sequences)
    return {
        "assignments": float(denominator),
        "coverage": totals["coverage"] / denominator,
        "stopped_cost_usd": totals["cost"] / denominator,
        "stopped_attempts": totals["attempts"] / denominator,
        "stopped_agent_steps": totals["agent_steps"] / denominator,
        "stopped_input_tokens": totals["input_tokens"] / denominator,
        "stopped_cache_tokens": totals["cache_tokens"] / denominator,
        "stopped_output_tokens": totals["output_tokens"] / denominator,
        "stopped_agent_seconds": totals["agent_seconds"] / denominator,
        "stopped_trial_seconds": totals["trial_seconds"] / denominator,
        "exact_agent_timeout_rate": totals["exact_agent_timeout"] / denominator,
    }


def aggregate_policy(rows: Sequence[TaskPolicySummary]) -> dict[str, float | int | None]:
    if not rows:
        raise ValueError("cannot aggregate an empty task basket")
    tasks = len(rows)
    successes = sum(row["coverage"] for row in rows)
    stopped_cost = sum(row["stopped_cost_usd"] for row in rows)
    output: dict[str, float | int | None] = {
        "tasks": tasks,
        "expected_verified_tasks": successes,
        "coverage": successes / tasks,
        "stopped_cost_per_task_usd": stopped_cost / tasks,
        "stopped_realized_cpsc_usd": stopped_cost / successes if successes else None,
        "stopped_attempts_per_task": sum(row["stopped_attempts"] for row in rows) / tasks,
        "stopped_agent_steps_per_task": (sum(row["stopped_agent_steps"] for row in rows) / tasks),
        "stopped_agent_hours_per_task": (
            sum(row["stopped_agent_seconds"] for row in rows) / tasks / 3600
        ),
        "stopped_trial_hours_per_task": (
            sum(row["stopped_trial_seconds"] for row in rows) / tasks / 3600
        ),
        "exact_agent_timeout_task_rate": (
            sum(row["exact_agent_timeout_rate"] for row in rows) / tasks
        ),
    }
    per_verified_fields = {
        "agent_steps": sum(row["stopped_agent_steps"] for row in rows),
        "agent_hours": sum(row["stopped_agent_seconds"] for row in rows) / 3600,
        "trial_hours": sum(row["stopped_trial_seconds"] for row in rows) / 3600,
    }
    for field, total in per_verified_fields.items():
        output[f"stopped_{field}_per_verified_task"] = total / successes if successes else None
    for field in ("input_tokens", "cache_tokens", "output_tokens"):
        total = sum(row[f"stopped_{field}"] for row in rows)
        output[f"stopped_{field}_per_verified_task"] = total / successes if successes else None
    return output


def contrast_metrics(
    candidate: Mapping[str, float | int | None],
    comparator: Mapping[str, float | int | None],
) -> dict[str, float | None]:
    candidate_cpsc = _optional_float(candidate["stopped_realized_cpsc_usd"])
    comparator_cpsc = _optional_float(comparator["stopped_realized_cpsc_usd"])
    return {
        "coverage_difference": float(candidate["coverage"]) - float(comparator["coverage"]),
        "stopped_cost_per_task_difference_usd": (
            float(candidate["stopped_cost_per_task_usd"])
            - float(comparator["stopped_cost_per_task_usd"])
        ),
        "stopped_cpsc_difference_usd": (
            candidate_cpsc - comparator_cpsc
            if candidate_cpsc is not None and comparator_cpsc is not None
            else None
        ),
        "stopped_cpsc_ratio": (
            candidate_cpsc / comparator_cpsc
            if candidate_cpsc is not None and comparator_cpsc not in (None, 0.0)
            else None
        ),
        "stopped_trial_hours_per_task_difference": (
            float(candidate["stopped_trial_hours_per_task"])
            - float(comparator["stopped_trial_hours_per_task"])
        ),
    }


def analyze(
    trials: dict[str, Any],
    tasks_payload: dict[str, Any],
    protocol: dict[str, Any],
    *,
    bootstrap_replicates: int,
    seed: int,
) -> dict[str, Any]:
    if bootstrap_replicates < 1:
        raise ValueError("bootstrap_replicates must be positive")
    source_rows = _required_rows(trials, "trials")
    task_rows = _required_rows(tasks_payload, "tasks")
    symbol_configs = {
        symbol: str(spec["config"])
        for symbol, spec in _required_object(protocol, "model_symbols").items()
    }
    policies = {
        str(row["id"]): tuple(str(symbol) for symbol in row["slots"])
        for row in _required_list(_required_object(protocol, "locked_policies"), "policies")
        if str(row["id"]) in PRIMARY_POLICY_IDS or str(row["id"]) in {"D0", "D1"}
    }
    missing_primary = set(PRIMARY_POLICY_IDS) - set(policies)
    if missing_primary:
        raise ValueError(f"protocol is missing primary policies: {sorted(missing_primary)}")

    scored_rows = [
        dict(row)
        for row in source_rows
        if row.get("source") == "deep-swe"
        and row.get("eval_scope") == "full"
        and row.get("included_in_score") is True
        and row.get("config") in set(symbol_configs.values())
    ]
    prepared_rows = _impute_configuration_mean_cost(scored_rows)
    attempts = _group_attempts(prepared_rows, symbol_configs)
    required_symbols = set().union(*(set(policies[policy_id]) for policy_id in PRIMARY_POLICY_IDS))
    common_tasks = sorted(
        set.intersection(
            *[
                {task for task, rows in attempts[symbol].items() if len(rows) == 4}
                for symbol in required_symbols
            ]
        )
    )
    if not common_tasks:
        raise ValueError("no tasks have four scored attempts for every primary policy symbol")
    task_to_repository = {
        str(row["id"]): str(row["repository"])
        for row in task_rows
        if isinstance(row, dict) and row.get("id") and row.get("repository")
    }
    missing_repository = sorted(set(common_tasks) - set(task_to_repository))
    if missing_repository:
        raise ValueError(f"tasks missing repository metadata: {missing_repository}")

    policy_task_rows = _summarize_policies(
        policies,
        attempts,
        common_tasks,
    )
    policy_results = {
        policy_id: aggregate_policy([policy_task_rows[policy_id][task] for task in common_tasks])
        for policy_id in policies
    }
    point_contrasts = {
        "P3_minus_P0": contrast_metrics(policy_results["P3"], policy_results["P0"]),
        "P3_minus_A0": contrast_metrics(policy_results["P3"], policy_results["A0"]),
    }
    point_contrasts["P3_minus_P0"]["task_coverage_difference_sd"] = stdev(
        policy_task_rows["P3"][task]["coverage"] - policy_task_rows["P0"][task]["coverage"]
        for task in common_tasks
    )
    point_contrasts["P3_minus_A0"]["task_coverage_difference_sd"] = stdev(
        policy_task_rows["P3"][task]["coverage"] - policy_task_rows["A0"][task]["coverage"]
        for task in common_tasks
    )

    repositories: dict[str, list[str]] = defaultdict(list)
    for task in common_tasks:
        repositories[task_to_repository[task]].append(task)
    frozen_bootstrap_seeds = bootstrap_seeds(seed)
    task_bootstrap = _bootstrap_contrasts(
        policy_task_rows,
        clusters=[[task] for task in common_tasks],
        replicates=bootstrap_replicates,
        seed=frozen_bootstrap_seeds["task_cluster"],
    )
    repository_bootstrap = _bootstrap_contrasts(
        policy_task_rows,
        clusters=[repositories[name] for name in sorted(repositories)],
        replicates=bootstrap_replicates,
        seed=frozen_bootstrap_seeds["repository_cluster"],
    )
    cache_sensitivity = _cache_sensitivity(
        policies=policies,
        attempts=attempts,
        common_tasks=common_tasks,
        policy_results=policy_results,
        protocol=protocol,
        all_scored_k3_rows=[
            row for row in prepared_rows if row.get("config") == symbol_configs["K"]
        ],
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": protocol.get("protocol_id"),
        "analysis_scope": "retrospective_discovery_reconstruction",
        "source_metadata": {
            "trials_generated_at": trials.get("generated_at"),
            "tasks_generated_at": tasks_payload.get("generated_at"),
        },
        "cohort": {
            "scored_selected_rows": len(prepared_rows),
            "common_complete_tasks": len(common_tasks),
            "repositories": len(repositories),
            "required_symbols": sorted(required_symbols),
            "excluded_incomplete_tasks": sorted(
                set().union(*(set(attempts[symbol]) for symbol in required_symbols))
                - set(common_tasks)
            ),
        },
        "policy_results": policy_results,
        "contrasts": point_contrasts,
        "bootstrap": {
            "replicates": bootstrap_replicates,
            "task_cluster": {
                "seed": frozen_bootstrap_seeds["task_cluster"],
                "contrasts": task_bootstrap,
            },
            "repository_cluster": {
                "seed": frozen_bootstrap_seeds["repository_cluster"],
                "clusters": len(repositories),
                "contrasts": repository_bootstrap,
            },
        },
        "cache_sensitivity": cache_sensitivity,
    }


def _summarize_policies(
    policies: Mapping[str, Sequence[str]],
    attempts: Mapping[str, Mapping[str, Sequence[Trial]]],
    tasks: Sequence[str],
    *,
    cache_fraction: float | None = None,
    k3_prices: Mapping[str, float] | None = None,
) -> dict[str, dict[str, TaskPolicySummary]]:
    output: dict[str, dict[str, TaskPolicySummary]] = {}
    for policy_id, slots in policies.items():
        output[policy_id] = {}
        for task in tasks:
            output[policy_id][task] = summarize_task_policy(
                slots,
                {symbol: attempts[symbol][task] for symbol in set(slots)},
                cache_fraction=cache_fraction,
                k3_prices=k3_prices,
            )
    return output


def _cache_sensitivity(
    *,
    policies: Mapping[str, Sequence[str]],
    attempts: Mapping[str, Mapping[str, Sequence[Trial]]],
    common_tasks: Sequence[str],
    policy_results: Mapping[str, Mapping[str, float | int | None]],
    protocol: Mapping[str, Any],
    all_scored_k3_rows: Sequence[Trial],
) -> dict[str, Any]:
    cache_plan = _required_object(protocol, "cache_accounting")
    price_rows = _required_object(cache_plan, "artifact_implied_prices_usd_per_million")
    k3_prices = {
        "uncached_input": float(price_rows["uncached_input"]),
        "cached_input": float(price_rows["cached_input"]),
        "output": float(price_rows["output"]),
    }
    successes = sum(bool(row.get("passed")) for row in all_scored_k3_rows)
    scenarios = []
    sensitivity_policies = {policy_id: policies[policy_id] for policy_id in ("P1", "P3")}
    for cache_fraction in configured_cache_fractions(protocol):
        task_rows = _summarize_policies(
            sensitivity_policies,
            attempts,
            common_tasks,
            cache_fraction=cache_fraction,
            k3_prices=k3_prices,
        )
        p1 = aggregate_policy([task_rows["P1"][task] for task in common_tasks])
        p3 = aggregate_policy([task_rows["P3"][task] for task in common_tasks])
        total_k3_cost = sum(
            k3_repriced_cost(
                row,
                cache_fraction=cache_fraction,
                uncached_input_per_1m=k3_prices["uncached_input"],
                cached_input_per_1m=k3_prices["cached_input"],
                output_per_1m=k3_prices["output"],
            )
            for row in all_scored_k3_rows
        )
        scenarios.append(
            {
                "cache_fraction": cache_fraction,
                "k3_scored_attempts": len(all_scored_k3_rows),
                "k3_successes": successes,
                "k3_mean_cost_per_attempt_usd": (
                    total_k3_cost / len(all_scored_k3_rows) if all_scored_k3_rows else None
                ),
                "k3_realized_cpsc_usd": total_k3_cost / successes if successes else None,
                "P1": p1,
                "P3": p3,
                "P3_minus_reported": contrast_metrics(p3, policy_results["P3"]),
                "P3_minus_P0": contrast_metrics(p3, policy_results["P0"]),
                "P3_minus_A0": contrast_metrics(p3, policy_results["A0"]),
            }
        )
    scenario_by_fraction = {row["cache_fraction"]: row for row in scenarios}
    zero = scenario_by_fraction[0.0]
    one = scenario_by_fraction[1.0]
    break_evens = {
        comparison: {
            field: linear_break_even_fraction(
                float(zero[comparison][field]),
                float(one[comparison][field]),
            )
            for field in (
                "stopped_cost_per_task_difference_usd",
                "stopped_cpsc_difference_usd",
            )
        }
        for comparison in ("P3_minus_P0", "P3_minus_A0")
    }
    return {
        "historical_cache_fraction_was_assumed_not_observed": True,
        "artifact_implied_prices_usd_per_million": k3_prices,
        "reported_P3": policy_results["P3"],
        "point_break_even_cache_fractions": break_evens,
        "scenarios": scenarios,
    }


def _bootstrap_contrasts(
    policy_task_rows: Mapping[str, Mapping[str, TaskPolicySummary]],
    *,
    clusters: Sequence[Sequence[str]],
    replicates: int,
    seed: int,
) -> dict[str, dict[str, float | int | None]]:
    rng = random.Random(seed)
    samples: dict[str, dict[str, list[float]]] = {
        contrast: defaultdict(list) for contrast in ("P3_minus_P0", "P3_minus_A0")
    }
    for _ in range(replicates):
        selected_tasks = [task for _ in clusters for task in clusters[rng.randrange(len(clusters))]]
        selected_results = {
            policy_id: aggregate_policy(
                [policy_task_rows[policy_id][task] for task in selected_tasks]
            )
            for policy_id in ("P0", "P3", "A0")
        }
        replicate_contrasts = {
            "P3_minus_P0": contrast_metrics(selected_results["P3"], selected_results["P0"]),
            "P3_minus_A0": contrast_metrics(selected_results["P3"], selected_results["A0"]),
        }
        for contrast, fields in replicate_contrasts.items():
            for field, value in fields.items():
                if value is not None:
                    samples[contrast][field].append(float(value))
    return {
        contrast: {
            field: {
                "defined_replicates": len(values),
                "ci_low": _percentile(sorted(values), 0.025),
                "ci_high": _percentile(sorted(values), 0.975),
            }
            for field, values in fields.items()
        }
        for contrast, fields in samples.items()
    }


def _impute_configuration_mean_cost(rows: Sequence[Trial]) -> list[Trial]:
    observed: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("cost_usd") is not None:
            observed[str(row["config"])].append(float(row["cost_usd"]))
    prepared = []
    for source in rows:
        row = dict(source)
        config = str(row["config"])
        cost = row.get("cost_usd")
        if cost is None:
            if not observed[config]:
                raise ValueError(f"configuration {config} has no observed cost")
            row["_analysis_cost_usd"] = sum(observed[config]) / len(observed[config])
            row["_cost_imputed"] = True
        else:
            row["_analysis_cost_usd"] = float(cost)
            row["_cost_imputed"] = False
        prepared.append(row)
    return prepared


def _group_attempts(
    rows: Sequence[Trial],
    symbol_configs: Mapping[str, str],
) -> dict[str, dict[str, list[Trial]]]:
    config_to_symbol = {config: symbol for symbol, config in symbol_configs.items()}
    grouped: dict[str, dict[str, list[Trial]]] = {
        symbol: defaultdict(list) for symbol in symbol_configs
    }
    for row in rows:
        symbol = config_to_symbol[str(row["config"])]
        grouped[symbol][str(row["task_name"])].append(row)
    return grouped


def _verify_artifact(path: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    payload = path.read_bytes()
    actual_sha256 = sha256(payload).hexdigest()
    actual_bytes = len(payload)
    if actual_sha256 != spec.get("sha256") or actual_bytes != int(spec.get("bytes", -1)):
        raise ValueError(
            f"artifact verification failed for {path}: bytes={actual_bytes}, sha256={actual_sha256}"
        )
    return {"path": str(path), "bytes": actual_bytes, "sha256": actual_sha256}


def _percentile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = probability * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + fraction * (values[upper] - values[lower])


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _required_rows(payload: Mapping[str, Any], label: str) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{label} artifact missing object rows list")
    return rows


def _required_object(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"missing object field: {field}")
    return value


def _required_list(payload: Mapping[str, Any], field: str) -> list[Any]:
    value = payload.get(field)
    if not isinstance(value, list):
        raise ValueError(f"missing list field: {field}")
    return value


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    protocol = _load_json_object(args.protocol)
    artifact_specs = {
        str(row["id"]): row
        for row in _required_list(_required_object(protocol, "source_snapshot"), "artifacts")
    }
    verification = {
        "trials": _verify_artifact(args.trials, artifact_specs["trials"]),
        "tasks": _verify_artifact(args.tasks, artifact_specs["tasks"]),
    }
    report = analyze(
        _load_json_object(args.trials),
        _load_json_object(args.tasks),
        protocol,
        bootstrap_replicates=args.bootstrap_replicates,
        seed=args.seed,
    )
    report["artifact_verification"] = verification
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

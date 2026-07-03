from __future__ import annotations

from pathlib import Path
import argparse
import json

from .budget import TokenBasis, estimate_panel_budget, load_panel
from .deepswe import (
    DEEPSWE_LEADERBOARD_URL,
    build_deepswe_comparison,
    load_deepswe_leaderboard,
)
from .pier_export import export_pier_job
from .results import aggregate_results, dump_results, load_prices, load_results
from .task_metadata import discover_tasks
from .workload import build_workload_index


def main() -> None:
    parser = argparse.ArgumentParser(prog="shallowswe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tasks_parser = subparsers.add_parser("tasks", help="list ShallowSWE task metadata")
    tasks_parser.add_argument("root", type=Path)

    export_parser = subparsers.add_parser("export-pier", help="export Pier job results")
    export_parser.add_argument("job_dir", type=Path)
    export_parser.add_argument("--tasks-root", type=Path, default=Path("tasks"))

    aggregate_parser = subparsers.add_parser("aggregate", help="summarize rollout results")
    aggregate_parser.add_argument("results_json", type=Path)
    aggregate_parser.add_argument(
        "--group-by",
        default="model_config,category,tier",
        help="comma-separated RolloutResult fields",
    )
    aggregate_parser.add_argument(
        "--prices",
        type=Path,
        help="versioned model price sheet used to derive dollar costs",
    )

    estimate_parser = subparsers.add_parser(
        "estimate-panel",
        help="estimate panel run cost from task count, rollouts, and token assumptions",
    )
    estimate_parser.add_argument("panel_json", type=Path)
    estimate_parser.add_argument(
        "--prices",
        action="append",
        type=Path,
        required=True,
        help="versioned model price sheet; may be supplied more than once",
    )
    estimate_parser.add_argument(
        "--tasks-root",
        type=Path,
        default=Path("tasks"),
        help="task root used to infer task count when --task-count is omitted",
    )
    estimate_parser.add_argument(
        "--task-count",
        type=int,
        help="override task count instead of discovering tasks from --tasks-root",
    )
    estimate_parser.add_argument("--rollouts", type=int, default=4)
    estimate_parser.add_argument("--input-tokens", type=int, default=10_000)
    estimate_parser.add_argument("--output-tokens", type=int, default=1_000)
    estimate_parser.add_argument("--cache-read-tokens", type=int, default=0)
    estimate_parser.add_argument("--cache-write-tokens", type=int, default=0)
    estimate_parser.add_argument("--peak-context-tokens", type=int, default=2_000)
    estimate_parser.add_argument(
        "--max-budget-usd",
        type=float,
        help="annotate whether the estimate exceeds this budget",
    )
    estimate_parser.add_argument(
        "--fail-over-budget",
        action="store_true",
        help="exit non-zero when --max-budget-usd is set and exceeded",
    )

    workload_parser = subparsers.add_parser(
        "workload-index",
        help="build site-ready declared-basket and slider data",
    )
    workload_parser.add_argument("results_json", type=Path)
    workload_parser.add_argument(
        "--prices",
        type=Path,
        help="versioned model price sheet used to derive dollar costs",
    )
    workload_parser.add_argument(
        "--target-tasks-per-cell",
        type=int,
        default=3,
        help="declared v1 task count per category-tier cell",
    )

    compare_parser = subparsers.add_parser(
        "compare-deepswe",
        help="join a ShallowSWE workload index to DeepSWE cost metadata",
    )
    compare_parser.add_argument("workload_index_json", type=Path)
    compare_parser.add_argument(
        "--deepswe",
        default=DEEPSWE_LEADERBOARD_URL,
        help="DeepSWE leaderboard JSON path or URL",
    )

    args = parser.parse_args()
    if args.command == "tasks":
        tasks = discover_tasks(args.root)
        print(
            json.dumps(
                [
                    {
                        "task_id": task.task_id,
                        "package_name": task.package_name,
                        "category": task.category,
                        "tier": task.tier,
                        "language": task.language,
                        "shape": task.shape,
                        "subtype": task.subtype,
                    }
                    for task in tasks
                ],
                indent=2,
            )
        )
        return

    if args.command == "export-pier":
        rows = export_pier_job(args.job_dir, args.tasks_root)
        print(dump_results(rows), end="")
        return

    if args.command == "aggregate":
        group_by = tuple(field.strip() for field in args.group_by.split(",") if field.strip())
        rows = load_results(args.results_json)
        prices = load_prices(args.prices) if args.prices else None
        print(json.dumps(aggregate_results(rows, group_by=group_by, prices=prices), indent=2))
        return

    if args.command == "estimate-panel":
        prices = {}
        for price_path in args.prices:
            prices.update(load_prices(price_path))
        task_count = args.task_count
        if task_count is None:
            task_count = len(discover_tasks(args.tasks_root))
        token_basis = TokenBasis(
            input_tokens=args.input_tokens,
            output_tokens=args.output_tokens,
            cache_read_tokens=args.cache_read_tokens,
            cache_write_tokens=args.cache_write_tokens,
            peak_context_tokens=args.peak_context_tokens,
        )
        estimate = estimate_panel_budget(
            load_panel(args.panel_json),
            prices,
            task_count=task_count,
            rollouts_per_task=args.rollouts,
            token_basis=token_basis,
            max_budget_usd=args.max_budget_usd,
        )
        print(json.dumps(estimate, indent=2))
        if args.fail_over_budget and estimate["over_budget"]:
            raise SystemExit(2)
        return

    if args.command == "workload-index":
        rows = load_results(args.results_json)
        prices = load_prices(args.prices) if args.prices else None
        print(
            json.dumps(
                build_workload_index(
                    rows,
                    prices=prices,
                    target_tasks_per_cell=args.target_tasks_per_cell,
                ),
                indent=2,
            )
        )
        return

    if args.command == "compare-deepswe":
        workload_index = json.loads(args.workload_index_json.read_text())
        leaderboard = load_deepswe_leaderboard(args.deepswe)
        print(json.dumps(build_deepswe_comparison(workload_index, leaderboard), indent=2))
        return

    raise AssertionError(f"unhandled command: {args.command}")

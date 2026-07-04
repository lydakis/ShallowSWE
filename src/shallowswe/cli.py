from __future__ import annotations

from pathlib import Path
import argparse
import json
import os

from .admission import audit_task_admission
from .budget import TokenBasis, estimate_panel_budget, load_panel
from .calibration import evaluate_one_shot_ceiling_gate, select_floor_pair
from .calibration_plan import audit_calibration_plan
from .deepswe import (
    DEEPSWE_LEADERBOARD_URL,
    build_deepswe_comparison,
    load_deepswe_leaderboard,
)
from .pier_export import export_pier_job
from .pier_repair_loop import (
    dump_repair_loop_rows,
    load_env_file,
    run_pier_repair_loop,
)
from .repair_loop_pilot import audit_repair_loop_pilot_plan
from .results import (
    aggregate_repair_loops,
    aggregate_results,
    dump_results,
    load_prices,
    load_repair_loops,
    load_results,
    merge_prices,
)
from .task_metadata import discover_tasks
from .workload import build_workload_index


def main() -> None:
    parser = argparse.ArgumentParser(prog="shallowswe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tasks_parser = subparsers.add_parser("tasks", help="list ShallowSWE task metadata")
    tasks_parser.add_argument("root", type=Path)

    admission_parser = subparsers.add_parser(
        "admission-audit",
        help="audit task-local evidence required before calibrated snapshot admission",
    )
    admission_parser.add_argument("root", type=Path)

    calibration_plan_parser = subparsers.add_parser(
        "calibration-plan",
        help="audit a pre-registered calibration run plan",
    )
    calibration_plan_parser.add_argument("plan_json", type=Path)

    repair_loop_pilot_parser = subparsers.add_parser(
        "repair-loop-pilot-plan",
        help="audit a bounded repair-loop pilot plan",
    )
    repair_loop_pilot_parser.add_argument("plan_json", type=Path)

    repair_loop_run_parser = subparsers.add_parser(
        "run-repair-loop-pilot",
        help="run one bounded repair-loop pilot row through Pier",
    )
    repair_loop_run_parser.add_argument("task_id")
    repair_loop_run_parser.add_argument("--tasks-root", type=Path, default=Path("tasks"))
    repair_loop_run_parser.add_argument(
        "--trials-dir",
        type=Path,
        default=Path("/tmp/shallowswe-pier-repair-loop-pilot"),
    )
    repair_loop_run_parser.add_argument("--job-name", default="shallowswe_repair_loop_pilot")
    repair_loop_run_parser.add_argument("--model", required=True)
    repair_loop_run_parser.add_argument(
        "--mini-swe-agent-source-dir",
        type=Path,
        default=Path.home() / "Developer" / "oss" / "mini-swe-agent",
    )
    repair_loop_run_parser.add_argument(
        "--config-file",
        type=Path,
        default=Path("configs") / "mini-swe-agent-calibration.yaml",
    )
    repair_loop_run_parser.add_argument("--reasoning-effort")
    repair_loop_run_parser.add_argument("--env-file", type=Path)
    repair_loop_run_parser.add_argument("--max-verifier-submissions", type=int, default=3)
    repair_loop_run_parser.add_argument("--dollar-cap-usd", type=float)
    repair_loop_run_parser.add_argument("--wall-time-cap-seconds", type=int)
    repair_loop_run_parser.add_argument("--seed", type=int, default=0)
    repair_loop_run_parser.add_argument("--output", type=Path)

    export_parser = subparsers.add_parser("export-pier", help="export Pier job results")
    export_parser.add_argument("job_dir", type=Path)
    export_parser.add_argument("--tasks-root", type=Path, default=Path("tasks"))

    aggregate_parser = subparsers.add_parser("aggregate", help="summarize rollout results")
    aggregate_parser.add_argument("results_json", type=Path)
    aggregate_parser.add_argument(
        "--group-by",
        default="model_config,category,size",
        help="comma-separated RolloutResult fields",
    )
    aggregate_parser.add_argument(
        "--prices",
        action="append",
        type=Path,
        help="versioned model price sheet; may be supplied more than once",
    )
    aggregate_repair_parser = subparsers.add_parser(
        "aggregate-repair-loops",
        help="summarize bounded repair-loop results",
    )
    aggregate_repair_parser.add_argument("results_json", type=Path)
    aggregate_repair_parser.add_argument(
        "--group-by",
        default="model_config,category,size",
        help="comma-separated RepairLoopResult fields",
    )
    aggregate_repair_parser.add_argument(
        "--prices",
        action="append",
        type=Path,
        help="versioned model price sheet; may be supplied more than once",
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
        action="append",
        type=Path,
        help="versioned model price sheet; may be supplied more than once",
    )
    workload_parser.add_argument(
        "--target-tasks-per-cell",
        type=int,
        default=4,
        help="declared v1 task count per category-size cell",
    )
    floor_parser = subparsers.add_parser(
        "select-floor",
        help="summarize floor-selection rollouts and recommend the measured floor pair",
    )
    floor_parser.add_argument("results_json", type=Path)
    floor_parser.add_argument(
        "--saturation-threshold",
        type=float,
        default=0.85,
        help="overall pass rate above which a pair is treated as saturated, not floor",
    )
    ceiling_parser = subparsers.add_parser(
        "ceiling-gate",
        help="evaluate one-shot ceiling acceptance against the pre-registered gate",
    )
    ceiling_parser.add_argument("results_json", type=Path)
    ceiling_parser.add_argument(
        "--pass-threshold",
        type=float,
        default=0.75,
        help="pre-registered one-shot ceiling pass threshold",
    )
    ceiling_parser.add_argument(
        "--target-rollouts",
        type=int,
        default=16,
        help="scored one-shot rollouts required before an admission decision",
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
                        "size": task.size,
                        "language": task.language,
                        "shape": task.shape,
                        "subtype": task.subtype,
                        "calibration_status": task.calibration_status,
                    }
                    for task in tasks
                ],
                indent=2,
            )
        )
        return

    if args.command == "admission-audit":
        print(json.dumps(audit_task_admission(args.root), indent=2))
        return

    if args.command == "calibration-plan":
        print(json.dumps(audit_calibration_plan(args.plan_json), indent=2))
        return

    if args.command == "repair-loop-pilot-plan":
        print(json.dumps(audit_repair_loop_pilot_plan(args.plan_json), indent=2))
        return

    if args.command == "run-repair-loop-pilot":
        agent_env = _load_agent_env(args.env_file)
        row = run_pier_repair_loop(
            task_path=args.tasks_root / args.task_id,
            trials_dir=args.trials_dir,
            trial_name=f"{args.job_name}__{args.task_id}",
            model_name=args.model,
            mini_swe_agent_source_dir=args.mini_swe_agent_source_dir,
            config_file=args.config_file,
            agent_env=agent_env,
            max_verifier_submissions=args.max_verifier_submissions,
            dollar_cap_usd=args.dollar_cap_usd,
            wall_time_cap_seconds=args.wall_time_cap_seconds,
            reasoning_effort=args.reasoning_effort,
            seed=args.seed,
        )
        output = dump_repair_loop_rows([row])
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output)
        else:
            print(output, end="")
        return

    if args.command == "export-pier":
        rows = export_pier_job(args.job_dir, args.tasks_root)
        print(dump_results(rows), end="")
        return

    if args.command == "aggregate":
        group_by = tuple(field.strip() for field in args.group_by.split(",") if field.strip())
        rows = load_results(args.results_json)
        prices = _load_price_catalog(args.prices)
        print(json.dumps(aggregate_results(rows, group_by=group_by, prices=prices), indent=2))
        return

    if args.command == "aggregate-repair-loops":
        group_by = tuple(field.strip() for field in args.group_by.split(",") if field.strip())
        rows = load_repair_loops(args.results_json)
        prices = _load_price_catalog(args.prices)
        print(
            json.dumps(
                aggregate_repair_loops(rows, group_by=group_by, prices=prices),
                indent=2,
            )
        )
        return

    if args.command == "estimate-panel":
        prices = merge_prices(*(load_prices(price_path) for price_path in args.prices))
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
        prices = _load_price_catalog(args.prices)
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

    if args.command == "select-floor":
        rows = load_results(args.results_json)
        print(
            json.dumps(
                select_floor_pair(
                    rows,
                    saturation_threshold=args.saturation_threshold,
                ),
                indent=2,
            )
        )
        return

    if args.command == "ceiling-gate":
        rows = load_results(args.results_json)
        print(
            json.dumps(
                evaluate_one_shot_ceiling_gate(
                    rows,
                    pass_threshold=args.pass_threshold,
                    target_rollouts=args.target_rollouts,
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


def _load_price_catalog(price_paths: list[Path] | None):
    if not price_paths:
        return None
    return merge_prices(*(load_prices(price_path) for price_path in price_paths))


def _load_agent_env(env_file: Path | None) -> dict[str, str]:
    keys = {"OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MSWEA_API_KEY"}
    values = {
        key: os.environ[key]
        for key in keys
        if os.environ.get(key)
    }
    if env_file:
        values.update(load_env_file(env_file, keys))
    return values

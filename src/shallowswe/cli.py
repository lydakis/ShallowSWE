from __future__ import annotations

from pathlib import Path
import argparse
import json

from .pier_export import export_pier_job
from .results import aggregate_results, dump_results, load_results
from .task_metadata import discover_tasks


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
        default="model,category,tier",
        help="comma-separated RolloutResult fields",
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
        print(json.dumps(aggregate_results(rows, group_by=group_by), indent=2))
        return

    raise AssertionError(f"unhandled command: {args.command}")

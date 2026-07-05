from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import re
import shutil
import tomllib

from shallowswe.results import (
    aggregate_repair_loops,
    load_prices,
    merge_prices,
    repair_loop_from_mapping,
)


CATEGORY_WEIGHTS = {"artifact": 34, "code": 33, "workflow": 33}
SIZE_WEIGHTS = {"small": 34, "medium": 33, "large": 33}


def main() -> None:
    args = _parse_args()
    run_dir = args.run_dir.resolve()
    repo = args.repo_root.resolve()
    public_data = args.site_dir.resolve() / "public" / "data"
    prices_path = args.prices.resolve()
    plan_path = args.plan.resolve()

    rows = _load_row_files(run_dir / "rows")
    prices = merge_prices(load_prices(prices_path))
    aggregate_by_model = aggregate_repair_loops(rows, group_by=("model_config",), prices=prices)
    aggregate_by_task_model = aggregate_repair_loops(
        rows,
        group_by=("model_config", "task_id"),
        prices=prices,
    )

    public_data.mkdir(parents=True, exist_ok=True)
    (public_data / "rollouts.json").write_text(
        json.dumps([asdict(row) for row in rows], indent=2) + "\n"
    )
    (public_data / "aggregate-by-model.json").write_text(
        json.dumps(aggregate_by_model, indent=2) + "\n"
    )
    (public_data / "aggregate-by-task-model.json").write_text(
        json.dumps(aggregate_by_task_model, indent=2) + "\n"
    )
    shutil.copy2(prices_path, public_data / f"prices-{prices_path.name}")
    if prices_path.name != "openrouter-2026-07-03.json":
        shutil.copy2(prices_path, public_data / "prices-openrouter-2026-07-03.json")
    else:
        shutil.copy2(prices_path, public_data / "prices-openrouter-2026-07-03.json")

    plan = json.loads(plan_path.read_text())
    report = _load_report(run_dir)
    _write_manifest(
        public_data / "run-manifest.json",
        plan=plan,
        report=report,
        run_dir=run_dir,
        repo=repo,
        rows_exported=len(rows),
    )

    workload_index = _build_workload_index(
        repo=repo,
        plan=plan,
        aggregate_by_task_model=aggregate_by_task_model,
    )
    (public_data / "workload-index.json").write_text(json.dumps(workload_index, indent=2) + "\n")
    _write_deepswe_comparison(public_data / "deepswe-comparison.json", workload_index)

    print(
        json.dumps(
            {
                "rows_exported": len(rows),
                "aggregate_models": len(aggregate_by_model),
                "aggregate_task_models": len(aggregate_by_task_model),
                "site_data": str(public_data),
            },
            indent=2,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export repair-loop rows to site JSON files.")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=Path("../ShallowSWE-www"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("configs/shallowswe-repair-loop-preview-n3-18.json"),
    )
    parser.add_argument(
        "--prices",
        type=Path,
        default=Path("prices/openrouter-2026-07-03.json"),
    )
    return parser.parse_args()


def _load_row_files(rows_dir: Path) -> list:
    rows = []
    for path in sorted(rows_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(raw, list):
            rows.extend(repair_loop_from_mapping(item) for item in raw)
    return rows


def _load_report(run_dir: Path) -> dict:
    path = run_dir / "repair-loop-run-report.json"
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text()))


def _write_manifest(
    path: Path,
    *,
    plan: dict,
    report: dict,
    run_dir: Path,
    repo: Path,
    rows_exported: int,
) -> None:
    try:
        source_output_dir = str(run_dir.relative_to(repo))
    except ValueError:
        source_output_dir = str(run_dir)
    path.write_text(
        json.dumps(
            {
                "schema_version": "shallowswe.repair_loop_site_manifest.v0.1",
                "name": f"{plan['name']}-clean",
                "snapshot_id": plan.get("snapshot_id"),
                "generated_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "status": "preview_partial_clean",
                "tasks": plan.get("task_ids", []),
                "repair_loop_seeds_per_task_model_config": plan.get(
                    "repair_loop_seeds_per_task_model_config"
                ),
                "repair_loop_policy": (
                    "N=3 bounded repair-loop preview; same model_config continues after "
                    "sanitized verifier feedback until pass or cap"
                ),
                "model_panel": plan.get("model_panel"),
                "agent": "shallowswe-resumable-mini-swe-agent",
                "runner": "Pier + ShallowSWE repair-loop controller",
                "protocol": plan.get("protocol"),
                "budget_gate": plan.get("budget_gate"),
                "run_report": {
                    "total_planned_rows": report.get("total_planned_rows"),
                    "completed_rows": rows_exported,
                    "skipped_existing_rows": report.get("skipped_existing_rows"),
                    "cumulative_spend_usd": report.get("cumulative_spend_usd"),
                    "stopped": report.get("stopped"),
                    "stop_reason": report.get("stop_reason"),
                    "parallelism": report.get("parallelism"),
                    "source_output_dir": source_output_dir,
                },
                "partial_rows_exported": rows_exported,
            },
            indent=2,
        )
        + "\n"
    )


def _build_workload_index(
    *,
    repo: Path,
    plan: dict,
    aggregate_by_task_model: list[dict[str, object]],
) -> dict:
    tasks = _task_metadata(repo, plan)
    task_counts_by_cell: dict[tuple[str, str], int] = defaultdict(int)
    for task in tasks.values():
        task_counts_by_cell[(task["category"], task["size"])] += 1

    by_model: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in aggregate_by_task_model:
        by_model[str(row["model_config"])].append(row)

    models = []
    for model_config, rows in sorted(by_model.items()):
        spend_numerator = 0.0
        token_numerator = 0.0
        solve_numerator = 0.0
        covered_weight = 0.0
        for row in rows:
            weight = _task_weight(
                str(row["task_id"]),
                tasks=tasks,
                task_counts_by_cell=task_counts_by_cell,
            )
            covered_weight += weight
            spend_numerator += weight * float(row.get("mean_cost_per_repair_loop") or 0)
            token_numerator += weight * float(row.get("mean_tokens_per_repair_loop") or 0)
            solve_numerator += weight * float(row.get("solve_rate") or 0)

        model, effort = _split_model_config(model_config)
        models.append(
            {
                "model_config": model_config,
                "model": model,
                "reasoning_effort": effort,
                "covered_weight": covered_weight,
                "weighted_solve_rate": solve_numerator / covered_weight
                if covered_weight
                else 0,
                "basket_cpsc": _ratio_or_none(spend_numerator, solve_numerator),
                "partial_basket_cpsc": _ratio_or_none(spend_numerator, solve_numerator),
                "basket_tokens_per_success": _ratio_or_none(
                    token_numerator,
                    solve_numerator,
                ),
                "partial_basket_tokens_per_success": _ratio_or_none(
                    token_numerator,
                    solve_numerator,
                ),
            }
        )

    return {
        "schema_version": "shallowswe.workload_index.repair_loop.v0.1",
        "weighting": {
            "scheme": "site_equal_category_equal_size_observed_task",
            "normalization": "partial_over_observed_clean_rows",
            "category_weights": CATEGORY_WEIGHTS,
            "size_weights": SIZE_WEIGHTS,
        },
        "models": models,
    }


def _task_metadata(repo: Path, plan: dict) -> dict[str, dict[str, str]]:
    tasks = {}
    for task_id in plan.get("task_ids", []):
        metadata = tomllib.loads((repo / "tasks" / task_id / "task.toml").read_text())[
            "metadata"
        ]
        tasks[str(task_id)] = {
            "category": str(metadata["category"]),
            "size": str(metadata["size"]),
        }
    return tasks


def _task_weight(
    task_id: str,
    *,
    tasks: dict[str, dict[str, str]],
    task_counts_by_cell: dict[tuple[str, str], int],
) -> float:
    task = tasks[task_id]
    category_total = sum(CATEGORY_WEIGHTS.values())
    size_total = sum(SIZE_WEIGHTS.values())
    return (
        CATEGORY_WEIGHTS[task["category"]]
        / category_total
        * SIZE_WEIGHTS[task["size"]]
        / size_total
        / task_counts_by_cell[(task["category"], task["size"])]
    )


def _write_deepswe_comparison(path: Path, workload_index: dict) -> None:
    existing = json.loads(path.read_text()) if path.exists() else {"rows": []}
    shallow_by_config = {
        item["model_config"]: item
        for item in workload_index.get("models", [])
        if isinstance(item, dict)
    }
    rows = []
    for row in existing.get("rows", []):
        new_row = dict(row)
        shallow = shallow_by_config.get(new_row.get("model_config"))
        new_row["shallowswe_basket_cpsc"] = shallow.get("basket_cpsc") if shallow else None
        new_row["shallowswe_partial_basket_cpsc"] = (
            shallow.get("partial_basket_cpsc") if shallow else None
        )
        new_row["shallowswe_basket_tokens_per_success"] = (
            shallow.get("basket_tokens_per_success") if shallow else None
        )
        new_row["shallowswe_covered_weight"] = shallow.get("covered_weight") if shallow else 0.0
        rows.append(new_row)

    rows.sort(
        key=lambda row: (
            row["shallowswe_basket_cpsc"] is None,
            float(row["shallowswe_basket_cpsc"] or 0),
            float(row.get("deepswe_cpsc") or 0),
            str(row.get("model_config")),
            str(row.get("deepswe_config")),
        )
    )
    path.write_text(
        json.dumps(
            {
                "schema_version": existing.get(
                    "schema_version",
                    "shallowswe.deepswe_comparison.v0.1",
                ),
                "deepswe_source": existing.get("deepswe_source"),
                "deepswe_generated_at": existing.get("deepswe_generated_at"),
                "shallowswe_schema_version": workload_index["schema_version"],
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )


def _split_model_config(model_config: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*)\[([^\]]+)\]$", model_config)
    if match:
        return match.group(1), match.group(2)
    return model_config, None


def _ratio_or_none(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


if __name__ == "__main__":
    main()

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
import json

from .budget import load_panel
from .pier_repair_loop import run_pier_repair_loop
from .repair_loop_preview import audit_repair_loop_preview_plan
from .results import (
    PriceCatalog,
    RepairLoopResult,
    dump_repair_loops,
    load_prices,
    load_repair_loops,
    merge_prices,
    repair_loop_cost_usd,
)


PREVIEW_BATCH_REPORT_SCHEMA_VERSION = "shallowswe.repair_loop_preview_batch.v0.1"

RepairLoopRunner = Callable[..., RepairLoopResult]


@dataclass(frozen=True)
class PreviewBatchItem:
    row_id: str
    task_id: str
    model_row_id: str
    model_name: str
    upstream_provider: str | None
    inference_gateway: str | None
    reasoning_effort: str | None
    seed: int
    trial_name: str
    output_path: Path


def build_repair_loop_preview_schedule(
    plan_path: Path,
    *,
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    job_name: str | None = None,
) -> list[PreviewBatchItem]:
    root = repo_root or Path.cwd()
    plan = json.loads(plan_path.read_text())
    panel = load_panel(_repo_path(root, str(plan["model_panel"])))
    model_rows = panel["rows"]
    if not isinstance(model_rows, list):
        raise ValueError("preview panel rows must be a list")

    task_ids = [str(task_id) for task_id in plan.get("task_ids", [])]
    seeds = int(plan.get("repair_loop_seeds_per_task_model_config") or 0)
    row_output_dir = (output_dir or default_preview_output_dir(plan, root=root)) / "rows"
    trial_prefix = job_name or str(plan.get("name") or "shallowswe-repair-loop-preview")

    schedule: list[PreviewBatchItem] = []
    for seed in range(seeds):
        for task_id in task_ids:
            for raw_row in model_rows:
                if not isinstance(raw_row, dict):
                    raise ValueError("preview panel row must be an object")
                model_row_id = _model_row_id(raw_row)
                row_id = f"seed-{seed:02d}__{task_id}__{_safe_id(model_row_id)}"
                schedule.append(
                    PreviewBatchItem(
                        row_id=row_id,
                        task_id=task_id,
                        model_row_id=model_row_id,
                        model_name=_model_name_for_panel_row(raw_row, panel),
                        upstream_provider=_optional_str(raw_row.get("upstream_provider")),
                        inference_gateway=_panel_gateway(raw_row, panel),
                        reasoning_effort=_optional_str(raw_row.get("reasoning_effort")),
                        seed=seed,
                        trial_name=f"{trial_prefix}__{row_id}",
                        output_path=row_output_dir / f"{row_id}.json",
                    )
                )
    return schedule


def default_preview_output_dir(plan: dict[str, Any], *, root: Path) -> Path:
    today = datetime.now(timezone.utc).date().isoformat()
    name = str(plan.get("name") or "shallowswe-repair-loop-preview")
    return root / "results" / f"{name}-{today}"


def run_repair_loop_preview_batch(
    plan_path: Path,
    *,
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    trials_dir: Path,
    mini_swe_agent_source_dir: Path,
    config_file: Path,
    agent_env: dict[str, str],
    price_paths: Iterable[Path] = (),
    job_name: str | None = None,
    max_rows: int | None = None,
    dry_run: bool = False,
    require_ready_to_launch: bool = True,
    parallelism: int = 1,
    runner: RepairLoopRunner = run_pier_repair_loop,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if parallelism < 1:
        raise ValueError("parallelism must be positive")

    root = repo_root or Path.cwd()
    plan = json.loads(plan_path.read_text())
    audit = audit_repair_loop_preview_plan(plan_path, repo_root=root)
    if require_ready_to_launch and not audit["ready_to_launch"]:
        raise ValueError(f"preview plan is not ready to launch: {audit}")

    selected_output_dir = output_dir or default_preview_output_dir(plan, root=root)
    selected_output_dir.mkdir(parents=True, exist_ok=True)
    combined_path = selected_output_dir / "repair-loop-results.json"
    report_path = selected_output_dir / "repair-loop-run-report.json"
    schedule = build_repair_loop_preview_schedule(
        plan_path,
        repo_root=root,
        output_dir=selected_output_dir,
        job_name=job_name,
    )
    if max_rows is not None:
        if max_rows < 1:
            raise ValueError("max_rows must be positive")
        schedule = schedule[:max_rows]

    prices = _load_prices(price_paths)
    protocol = plan.get("protocol") if isinstance(plan.get("protocol"), dict) else {}
    budget_gate = plan.get("budget_gate") if isinstance(plan.get("budget_gate"), dict) else {}
    per_row_dollar_cap = _optional_float(protocol.get("dollar_cap_usd"))
    global_hard_stop = _optional_float(budget_gate.get("global_hard_stop_usd"))
    max_verifier_submissions = int(protocol.get("verifier_submission_cap") or 0)
    wall_time_cap_seconds = _optional_int(protocol.get("wall_time_cap_seconds"))
    task_root = _repo_path(root, str(plan.get("task_root") or "tasks"))

    completed: dict[str, RepairLoopResult] = {}
    skipped_existing = 0
    for item in schedule:
        existing_row = _load_existing_row(item.output_path)
        if existing_row is None:
            continue
        completed[item.row_id] = existing_row
        skipped_existing += 1

    cumulative_spend = _cumulative_spend(completed.values(), prices)
    report = _batch_report(
        plan=plan,
        audit=audit,
        output_dir=selected_output_dir,
        combined_path=combined_path,
        report_path=report_path,
        schedule=schedule,
        completed=completed,
        skipped_existing=skipped_existing,
        cumulative_spend_usd=cumulative_spend,
        global_hard_stop_usd=global_hard_stop,
        dry_run=dry_run,
        parallelism=parallelism,
        stopped=False,
        stop_reason=None,
    )
    _write_combined_results(schedule, completed, combined_path)
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    if dry_run:
        return report

    if max_verifier_submissions < 1:
        raise ValueError("preview protocol must set a positive verifier_submission_cap")

    pending = [item for item in schedule if item.row_id not in completed]
    pending_index = 0
    in_flight: dict[Future[RepairLoopResult], PreviewBatchItem] = {}
    reserved_spend = 0.0
    stopped = False
    stop_reason = None
    row_cap_reserve = per_row_dollar_cap or 0.0

    executor_cls = (
        ProcessPoolExecutor
        if parallelism > 1 and runner is run_pier_repair_loop
        else ThreadPoolExecutor
    )

    with executor_cls(max_workers=parallelism) as executor:
        while pending_index < len(pending) or in_flight:
            while not stopped and pending_index < len(pending) and len(in_flight) < parallelism:
                if _would_exceed_hard_stop(
                    cumulative_spend_usd=cumulative_spend + reserved_spend,
                    global_hard_stop_usd=global_hard_stop,
                    next_row_cap_usd=per_row_dollar_cap,
                ):
                    stopped = True
                    stop_reason = "global_hard_stop"
                    break

                item = pending[pending_index]
                pending_index += 1
                reserved_spend += row_cap_reserve
                if progress:
                    progress(
                        "running "
                        f"{len(completed) + len(in_flight) + 1}/{len(schedule)} "
                        f"{item.task_id} {item.model_name}"
                        f"{f'[{item.reasoning_effort}]' if item.reasoning_effort else ''} "
                        f"seed={item.seed} spend=${cumulative_spend:.4f}"
                    )
                future = executor.submit(
                    runner,
                    task_path=task_root / item.task_id,
                    trials_dir=trials_dir,
                    trial_name=item.trial_name,
                    model_name=item.model_name,
                    mini_swe_agent_source_dir=mini_swe_agent_source_dir,
                    config_file=config_file,
                    agent_env=agent_env,
                    max_verifier_submissions=max_verifier_submissions,
                    dollar_cap_usd=per_row_dollar_cap,
                    wall_time_cap_seconds=wall_time_cap_seconds,
                    reasoning_effort=item.reasoning_effort,
                    seed=item.seed,
                )
                in_flight[future] = item

            if not in_flight:
                break

            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                item = in_flight.pop(future)
                reserved_spend -= row_cap_reserve
                row = _annotate_row(future.result(), item=item, plan=plan)
                item.output_path.parent.mkdir(parents=True, exist_ok=True)
                item.output_path.write_text(dump_repair_loops([row]))
                completed[item.row_id] = row
                cumulative_spend = _cumulative_spend(completed.values(), prices)
                _write_combined_results(schedule, completed, combined_path)
                report = _batch_report(
                    plan=plan,
                    audit=audit,
                    output_dir=selected_output_dir,
                    combined_path=combined_path,
                    report_path=report_path,
                    schedule=schedule,
                    completed=completed,
                    skipped_existing=skipped_existing,
                    cumulative_spend_usd=cumulative_spend,
                    global_hard_stop_usd=global_hard_stop,
                    dry_run=dry_run,
                    parallelism=parallelism,
                    stopped=stopped,
                    stop_reason=stop_reason,
                    last_row=row,
                )
                report_path.write_text(json.dumps(report, indent=2) + "\n")

    if stopped:
        report = _batch_report(
            plan=plan,
            audit=audit,
            output_dir=selected_output_dir,
            combined_path=combined_path,
            report_path=report_path,
            schedule=schedule,
            completed=completed,
            skipped_existing=skipped_existing,
            cumulative_spend_usd=cumulative_spend,
            global_hard_stop_usd=global_hard_stop,
            dry_run=dry_run,
            parallelism=parallelism,
            stopped=True,
            stop_reason=stop_reason,
        )
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    return report


def preview_row_spend_usd(
    row: RepairLoopResult,
    prices: PriceCatalog | None,
) -> float:
    candidates: list[float] = []
    if row.gateway_reported_cost_usd is not None:
        candidates.append(row.gateway_reported_cost_usd)
    if prices:
        try:
            candidates.append(repair_loop_cost_usd(row, prices))
        except ValueError:
            pass
    return max(candidates) if candidates else 0.0


def _batch_report(
    *,
    plan: dict[str, Any],
    audit: dict[str, Any],
    output_dir: Path,
    combined_path: Path,
    report_path: Path,
    schedule: list[PreviewBatchItem],
    completed: dict[str, RepairLoopResult],
    skipped_existing: int,
    cumulative_spend_usd: float,
    global_hard_stop_usd: float | None,
    dry_run: bool,
    parallelism: int,
    stopped: bool,
    stop_reason: str | None,
    last_row: RepairLoopResult | None = None,
) -> dict[str, Any]:
    successes = sum(1 for row in completed.values() if row.is_scored and row.passed)
    scored = sum(1 for row in completed.values() if row.is_scored)
    return {
        "schema_version": PREVIEW_BATCH_REPORT_SCHEMA_VERSION,
        "plan": plan.get("name"),
        "snapshot_id": plan.get("snapshot_id"),
        "audit_ready_to_launch": audit.get("ready_to_launch"),
        "output_dir": str(output_dir),
        "combined_results_path": str(combined_path),
        "report_path": str(report_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "parallelism": parallelism,
        "total_planned_rows": len(schedule),
        "completed_rows": len(completed),
        "remaining_rows": len(schedule) - len(completed),
        "skipped_existing_rows": skipped_existing,
        "scored_rows": scored,
        "successes": successes,
        "solve_rate_so_far": successes / scored if scored else None,
        "cumulative_spend_usd": cumulative_spend_usd,
        "global_hard_stop_usd": global_hard_stop_usd,
        "remaining_budget_usd": (
            global_hard_stop_usd - cumulative_spend_usd
            if global_hard_stop_usd is not None
            else None
        ),
        "stopped": stopped,
        "stop_reason": stop_reason,
        "last_row": asdict(last_row) if last_row else None,
    }


def _annotate_row(
    row: RepairLoopResult,
    *,
    item: PreviewBatchItem,
    plan: dict[str, Any],
) -> RepairLoopResult:
    return replace(
        row,
        model=item.model_name,
        inference_gateway=item.inference_gateway or row.inference_gateway,
        upstream_provider=item.upstream_provider or row.upstream_provider,
        requested_model=item.model_name,
        reasoning_effort=item.reasoning_effort or row.reasoning_effort,
        task_suite_version=str(plan.get("snapshot_id") or row.task_suite_version),
    )


def _write_combined_results(
    schedule: list[PreviewBatchItem],
    completed: dict[str, RepairLoopResult],
    combined_path: Path,
) -> None:
    combined_path.write_text(
        dump_repair_loops(
            row
            for item in schedule
            if (row := completed.get(item.row_id)) is not None
        )
    )


def _load_existing_row(path: Path) -> RepairLoopResult | None:
    if not path.exists():
        return None
    rows = load_repair_loops(path)
    if len(rows) != 1:
        raise ValueError(f"{path} must contain exactly one repair-loop row")
    return rows[0]


def _cumulative_spend(
    rows: Iterable[RepairLoopResult],
    prices: PriceCatalog | None,
) -> float:
    return sum(preview_row_spend_usd(row, prices) for row in rows if row.is_scored)


def _would_exceed_hard_stop(
    *,
    cumulative_spend_usd: float,
    global_hard_stop_usd: float | None,
    next_row_cap_usd: float | None,
) -> bool:
    if global_hard_stop_usd is None:
        return False
    reserve = next_row_cap_usd or 0.0
    return cumulative_spend_usd + reserve > global_hard_stop_usd


def _load_prices(price_paths: Iterable[Path]) -> PriceCatalog | None:
    paths = list(price_paths)
    if not paths:
        return None
    return merge_prices(*(load_prices(path) for path in paths))


def _model_row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("model") or row.get("openrouter_model") or "unknown")


def _model_name_for_panel_row(row: dict[str, Any], panel: dict[str, Any]) -> str:
    gateway = _panel_gateway(row, panel)
    gateway_model_key = f"{gateway}_model" if gateway else None
    model = (
        row.get(gateway_model_key)
        if gateway_model_key and row.get(gateway_model_key)
        else row.get("openrouter_model") or row.get("model")
    )
    if not model:
        raise ValueError("panel row missing model")
    model_name = str(model)
    if gateway and not model_name.startswith(f"{gateway}/"):
        return f"{gateway}/{model_name}"
    return model_name


def _panel_gateway(row: dict[str, Any], panel: dict[str, Any]) -> str | None:
    if row.get("inference_gateway"):
        return str(row["inference_gateway"])
    defaults = panel.get("defaults")
    if isinstance(defaults, dict) and defaults.get("inference_gateway"):
        return str(defaults["inference_gateway"])
    return None


def _repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _optional_str(value: object | None) -> str | None:
    return str(value) if value is not None else None


def _optional_float(value: object | None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _optional_int(value: object | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            safe.append(char)
        else:
            safe.append("-")
    return "".join(safe).strip("-") or "unknown"

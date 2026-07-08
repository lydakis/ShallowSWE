from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


AGENT_IMPORT_PATH = "shallowswe.pier_agents.codex_subscription_agent:CodexSubscriptionAgent"
CODEX_VERSION = "0.142.0"
SCHEMA_VERSION = "shallowswe.codex_subscription_sizing.v0.2"
CODEX_EFFORTS = ("medium", "high", "xhigh")
FORMAL_CEILING_EFFORT = "xhigh"


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd()
    tasks_root = (repo_root / args.tasks_root).resolve()
    jobs_dir = Path(args.jobs_dir).resolve()

    if args.report_only:
        regenerate_report(
            results_dir=args.report_only.resolve(),
            tasks_root=tasks_root,
        )
        return 0

    if args.progress_only:
        write_progress(
            results_dir=args.progress_only.resolve(),
        )
        return 0

    stamp = args.stamp or datetime.now().strftime("%Y-%m-%d-%H%M%S")
    results_dir = (repo_root / args.results_root / f"shallowswe-codex-subscription-sizing-{stamp}")
    results_dir.mkdir(parents=True, exist_ok=True)
    log_path = results_dir / "runner.log"

    env = codex_subscription_env()
    task_metadata = load_task_metadata(tasks_root, log_path, env)
    if args.include_task_name:
        task_metadata = filter_task_metadata(task_metadata, args.include_task_name)
    all_task_ids = [row["task_id"] for row in task_metadata]
    if args.excluded_retries < 0:
        raise SystemExit("--excluded-retries must be non-negative")

    status: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stamp": stamp,
        "task_count": len(all_task_ids),
        "task_ids": all_task_ids,
        "jobs_dir": str(jobs_dir),
        "results_dir": str(results_dir),
        "stages": {},
    }
    write_json(results_dir / "status.json", status)

    ceiling_rows_by_effort: dict[str, list[dict[str, Any]]] = {}
    rows, ceiling_stage_run = run_ceiling_effort(
        effort=args.ceiling_effort,
        stamp=stamp,
        results_dir=results_dir,
        tasks_root=tasks_root,
        jobs_dir=jobs_dir,
        task_ids=all_task_ids,
        log_path=log_path,
        env=env,
        concurrency=args.concurrency,
        excluded_retries=args.excluded_retries,
        attempts=args.ceiling_attempts,
    )
    ceiling_rows_by_effort[args.ceiling_effort] = rows
    ceiling_failures = failed_task_ids(rows)
    tasks_without_scored_attempt = task_ids_without_scored_rows(rows, ceiling_stage_run["task_ids"])
    if args.ceiling_effort == FORMAL_CEILING_EFFORT:
        status["formal_ceiling"] = {
            "model": "openai/gpt-5.5",
            "reasoning_effort": FORMAL_CEILING_EFFORT,
            "model_config": model_config("openai/gpt-5.5", FORMAL_CEILING_EFFORT),
            "attempts_per_task": args.ceiling_attempts,
            "role": "formal ceiling probe",
        }
    else:
        status["formal_ceiling"] = {
            "model": "openai/gpt-5.5",
            "reasoning_effort": FORMAL_CEILING_EFFORT,
            "model_config": model_config("openai/gpt-5.5", FORMAL_CEILING_EFFORT),
            "attempts_per_task": args.ceiling_attempts,
            "role": "formal ceiling probe",
            "status": "not_run",
            "note": (
                f"gpt-5.5[{args.ceiling_effort}] was run as smoke only; "
                "formal admission still requires Extra High."
            ),
        }
        status["practical_smoke"] = {
            "model": "openai/gpt-5.5",
            "reasoning_effort": args.ceiling_effort,
            "model_config": model_config("openai/gpt-5.5", args.ceiling_effort),
            "attempts_per_task": args.ceiling_attempts,
            "role": "diagnostic smoke probe",
        }
    status["stages"][f"ceiling_{args.ceiling_effort}"] = {
        "status": "complete",
        "job_name": ceiling_stage_run["job_names"][0] if ceiling_stage_run["job_names"] else None,
        "job_names": ceiling_stage_run["job_names"],
        "rollouts": str(ceiling_stage_run["combined_rollouts_path"]),
        "rollout_paths": ceiling_stage_run["rollout_paths"],
        "task_count": len({row["task_id"] for row in rows}),
        "scored_task_count": len(scored_task_ids(rows)),
        "failed_task_count": len(ceiling_failures),
        "attempts_per_task": args.ceiling_attempts,
        "tasks_without_scored_attempt": tasks_without_scored_attempt,
        "excluded_retry_count": ceiling_stage_run["excluded_retry_count"],
    }
    write_json(results_dir / "status.json", status)

    floor_job_name = f"shallowswe_codex_sub_sizing_{stamp}_floor_gpt54mini_low_n{args.floor_attempts}"
    run_pier_job(
        tasks_root=tasks_root,
        jobs_dir=jobs_dir,
        job_name=floor_job_name,
        model="openai/gpt-5.4-mini",
        reasoning_effort="low",
        attempts=args.floor_attempts,
        task_ids=all_task_ids,
        log_path=log_path,
        env=env,
        concurrency=args.concurrency,
    )
    floor_rollouts_path = results_dir / "floor-gpt54mini-low-rollouts.json"
    export_pier_job(jobs_dir / floor_job_name, tasks_root, floor_rollouts_path, log_path, env)
    floor_rows = load_rows(floor_rollouts_path)
    status["stages"]["floor_gpt54mini_low"] = {
        "status": "complete",
        "job_name": floor_job_name,
        "rollouts": str(floor_rollouts_path),
        "task_count": len({row["task_id"] for row in floor_rows}),
        "attempts_per_task": args.floor_attempts,
    }
    write_json(results_dir / "status.json", status)

    report = build_report(
        task_metadata=task_metadata,
        ceiling_rows_by_effort=ceiling_rows_by_effort,
        floor_rows=floor_rows,
        status=status,
    )
    write_json(results_dir / "codex-subscription-sizing-report.json", report)
    write_markdown_summary(results_dir / "summary.md", report)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Codex subscription sizing probes through Pier."
    )
    parser.add_argument("--tasks-root", default="tasks")
    parser.add_argument("--jobs-dir", default="/tmp/shallowswe-pier")
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--stamp")
    parser.add_argument("--floor-attempts", type=int, default=3)
    parser.add_argument(
        "--ceiling-effort",
        choices=CODEX_EFFORTS,
        default=FORMAL_CEILING_EFFORT,
        help=(
            "Reasoning effort for the gpt-5.5 probe. Only xhigh, recorded as "
            "openai/gpt-5.5[extra_high], is formal ceiling evidence; medium/high "
            "are diagnostic smoke rows."
        ),
    )
    parser.add_argument("--ceiling-attempts", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--include-task-name",
        action="append",
        default=[],
        help="Restrict the sizing run to one task ID. Repeat for multiple tasks.",
    )
    parser.add_argument(
        "--excluded-retries",
        type=int,
        default=1,
        help="same-effort retries for tasks whose exported rows are all excluded",
    )
    parser.add_argument(
        "--report-only",
        type=Path,
        help="Regenerate report artifacts from an existing sizing results directory.",
    )
    parser.add_argument(
        "--progress-only",
        type=Path,
        help="Refresh progress.json from existing Pier job directories.",
    )
    return parser.parse_args()


def codex_subscription_env() -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_FORCE_AUTH_JSON"] = "true"
    env.pop("OPENAI_API_KEY", None)
    env.pop("CODEX_API_KEY", None)
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        raise SystemExit(f"Missing Codex auth file: {auth_path}")
    auth = json.loads(auth_path.read_text())
    if auth.get("auth_mode") != "chatgpt":
        raise SystemExit(f"Codex auth_mode must be chatgpt, got {auth.get('auth_mode')!r}")
    return env


def filter_task_metadata(
    task_metadata: list[dict[str, Any]],
    include_task_names: list[str],
) -> list[dict[str, Any]]:
    requested_task_ids = sorted(set(include_task_names))
    known_task_ids = {row["task_id"] for row in task_metadata}
    unknown_task_ids = sorted(set(requested_task_ids) - known_task_ids)
    if unknown_task_ids:
        raise SystemExit(f"Unknown task IDs requested: {', '.join(unknown_task_ids)}")
    return [
        row
        for row in task_metadata
        if row["task_id"] in requested_task_ids
    ]


def load_task_metadata(
    tasks_root: Path,
    log_path: Path,
    env: dict[str, str],
) -> list[dict[str, Any]]:
    cmd = ["uv", "run", "shallowswe", "tasks", str(tasks_root)]
    with log_path.open("a") as log:
        log.write(f"$ {shlex.join(cmd)}\n")
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            check=True,
        )
    return json.loads(result.stdout)


def run_pier_job(
    *,
    tasks_root: Path,
    jobs_dir: Path,
    job_name: str,
    model: str,
    reasoning_effort: str,
    attempts: int,
    task_ids: list[str],
    log_path: Path,
    env: dict[str, str],
    concurrency: int,
) -> None:
    cmd = [
        "uv",
        "run",
        "pier",
        "run",
        "--path",
        str(tasks_root),
        "--job-name",
        job_name,
        "--jobs-dir",
        str(jobs_dir),
        "--n-attempts",
        str(attempts),
        "--n-concurrent",
        str(concurrency),
        "--agent-import-path",
        AGENT_IMPORT_PATH,
        "--model",
        model,
        "--agent-kwarg",
        f"version={CODEX_VERSION}",
        "--agent-kwarg",
        f"reasoning_effort={reasoning_effort}",
        "--agent-env",
        "CODEX_FORCE_AUTH_JSON=true",
        "--env",
        "docker",
        "--yes",
        "--max-retries",
        "1",
        "--quiet",
    ]
    for task_id in task_ids:
        cmd.extend(["--include-task-name", task_id])

    with log_path.open("a") as log:
        log.write(f"$ {shlex.join(cmd)}\n")
        log.flush()
        subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, text=True, check=True)


def run_ceiling_effort(
    *,
    effort: str,
    stamp: str,
    results_dir: Path,
    tasks_root: Path,
    jobs_dir: Path,
    task_ids: list[str],
    log_path: Path,
    env: dict[str, str],
    concurrency: int,
    excluded_retries: int,
    attempts: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    combined_rows: list[dict[str, Any]] = []
    pending_task_ids = list(task_ids)
    job_names: list[str] = []
    rollout_paths: list[str] = []

    for retry_index in range(excluded_retries + 1):
        if not pending_task_ids:
            break

        retry_suffix = "" if retry_index == 0 else f"_retry{retry_index}"
        file_suffix = "" if retry_index == 0 else f"-retry{retry_index}"
        job_name = (
            f"shallowswe_codex_sub_sizing_{stamp}_ceiling_gpt55_{effort}_n{attempts}"
            f"{retry_suffix}"
        )
        rollouts_path = results_dir / f"ceiling-gpt55-{effort}{file_suffix}-rollouts.json"
        run_pier_job(
            tasks_root=tasks_root,
            jobs_dir=jobs_dir,
            job_name=job_name,
            model="openai/gpt-5.5",
            reasoning_effort=effort,
            attempts=attempts,
            task_ids=pending_task_ids,
            log_path=log_path,
            env=env,
            concurrency=concurrency,
        )
        export_pier_job(jobs_dir / job_name, tasks_root, rollouts_path, log_path, env)
        rows = load_rows(rollouts_path)
        combined_rows.extend(rows)
        job_names.append(job_name)
        rollout_paths.append(str(rollouts_path))
        pending_task_ids = task_ids_without_scored_rows(rows, pending_task_ids)

    combined_rollouts_path = results_dir / f"ceiling-gpt55-{effort}-rollouts.json"
    if len(rollout_paths) > 1:
        write_json(combined_rollouts_path, combined_rows)
    return (
        combined_rows,
        {
            "task_ids": list(task_ids),
            "job_names": job_names,
            "rollout_paths": rollout_paths,
            "combined_rollouts_path": combined_rollouts_path,
            "excluded_retry_count": max(0, len(job_names) - 1),
        },
    )


def export_pier_job(
    job_dir: Path,
    tasks_root: Path,
    output_path: Path,
    log_path: Path,
    env: dict[str, str],
) -> None:
    cmd = ["uv", "run", "shallowswe", "export-pier", str(job_dir), "--tasks-root", str(tasks_root)]
    with log_path.open("a") as log, output_path.open("w") as output:
        log.write(f"$ {shlex.join(cmd)} > {output_path}\n")
        log.flush()
        subprocess.run(cmd, env=env, stdout=output, stderr=log, text=True, check=True)


def load_rows(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def failed_task_ids(rows: list[dict[str, Any]]) -> list[str]:
    return scored_failed_task_ids(rows)


def scored_failed_task_ids(rows: list[dict[str, Any]]) -> list[str]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not is_scored_row(row):
            continue
        by_task[row["task_id"]].append(row)
    return sorted(
        task_id
        for task_id, task_rows in by_task.items()
        if not any(bool(row.get("passed")) for row in task_rows)
    )


def task_ids_without_scored_rows(
    rows: list[dict[str, Any]],
    task_ids: list[str],
) -> list[str]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    return [
        task_id
        for task_id in task_ids
        if not any(is_scored_row(row) for row in by_task.get(task_id, []))
    ]


def scored_task_ids(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({row["task_id"] for row in rows if is_scored_row(row)})


def is_scored_row(row: dict[str, Any]) -> bool:
    return row.get("status", "scored") != "excluded"


def build_report(
    *,
    task_metadata: list[dict[str, Any]],
    ceiling_rows_by_effort: dict[str, list[dict[str, Any]]],
    floor_rows: list[dict[str, Any]],
    status: dict[str, Any],
) -> dict[str, Any]:
    formal_effort = formal_ceiling_effort(status, ceiling_rows_by_effort)
    formal_by_task = group_by_task(ceiling_rows_by_effort.get(formal_effort, []))
    medium_by_task = group_by_task(ceiling_rows_by_effort.get("medium", []))
    floor_by_task = group_by_task(floor_rows)
    tasks = []
    for meta in task_metadata:
        task_id = meta["task_id"]
        formal_summary = rollout_summary(formal_by_task.get(task_id, []))
        medium_smoke = rollout_summary(medium_by_task.get(task_id, []))

        floor_task_rows = floor_by_task.get(task_id, [])
        scored_floor_task_rows = [row for row in floor_task_rows if is_scored_row(row)]
        floor_passes = sum(1 for row in scored_floor_task_rows if row.get("passed"))
        floor_attempts = len(scored_floor_task_rows)
        floor_pass_rate = floor_passes / floor_attempts if floor_attempts else None
        tasks.append(
            {
                "task_id": task_id,
                "category": meta["category"],
                "metadata_size": meta["size"],
                "calibration_status": meta["calibration_status"],
                "codex_5_5_formal_ceiling_effort": formal_effort,
                "codex_5_5_formal_ceiling": formal_summary,
                "codex_5_5_medium_smoke": medium_smoke,
                "codex_5_4_mini_low_attempts": floor_attempts,
                "codex_5_4_mini_low_passes": floor_passes,
                "codex_5_4_mini_low_pass_rate": floor_pass_rate,
                "codex_5_4_mini_low_excluded": len(floor_task_rows) - floor_attempts,
                "provisional_floor_size": provisional_floor_size(floor_pass_rate),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "formal_ceiling": {
            "model": "openai/gpt-5.5",
            "reasoning_effort": formal_effort,
            "model_config": model_config("openai/gpt-5.5", formal_effort),
            "role": "formal ceiling probe",
            "rule": "Only the configured formal ceiling effort counts as ceiling evidence.",
        },
        "practical_smoke": {
            "model": "openai/gpt-5.5",
            "reasoning_effort": "medium",
            "model_config": model_config("openai/gpt-5.5", "medium"),
            "role": "optional low-spend smoke signal only",
            "rule": "Medium smoke rows do not satisfy the formal ceiling gate.",
        },
        "floor_probe": {
            "model": "openai/gpt-5.4-mini",
            "reasoning_effort": "low",
            "attempts_per_task": floor_attempts_per_task(status, floor_rows),
            "size_rule": "N=3 provisional: >=0.70 small, >=0.30 medium, otherwise large.",
        },
        "tasks": tasks,
    }


def infer_formal_effort() -> str:
    return FORMAL_CEILING_EFFORT


def formal_ceiling_effort(
    status: dict[str, Any],
    ceiling_rows_by_effort: dict[str, list[dict[str, Any]]],
) -> str:
    configured = str((status.get("formal_ceiling") or {}).get("reasoning_effort") or "")
    if configured == FORMAL_CEILING_EFFORT:
        return configured
    if configured:
        return FORMAL_CEILING_EFFORT
    return infer_formal_effort()


def model_config(model: str, effort: str) -> str:
    display_effort = "extra_high" if effort == "xhigh" else effort
    return f"{model}[{display_effort}]"


def regenerate_report(*, results_dir: Path, tasks_root: Path) -> None:
    env = codex_subscription_env()
    status_path = results_dir / "status.json"
    if not status_path.exists():
        raise SystemExit(f"Missing status file: {status_path}")
    status = json.loads(status_path.read_text())
    task_metadata = load_task_metadata(tasks_root, results_dir / "runner.log", env)
    ceiling_rows_by_effort = {
        effort: load_optional_rows(results_dir / f"ceiling-gpt55-{effort}-rollouts.json")
        for effort in ("medium", "high", "xhigh")
    }
    floor_rows = load_optional_rows(results_dir / "floor-gpt54mini-low-rollouts.json")
    report_task_ids = status.get("task_ids") or sorted(
        {
            row["task_id"]
            for rows in [*ceiling_rows_by_effort.values(), floor_rows]
            for row in rows
        }
    )
    if report_task_ids:
        task_metadata = filter_task_metadata(task_metadata, list(report_task_ids))
    report = build_report(
        task_metadata=task_metadata,
        ceiling_rows_by_effort=ceiling_rows_by_effort,
        floor_rows=floor_rows,
        status=status,
    )
    write_json(results_dir / "codex-subscription-sizing-report.json", report)
    write_markdown_summary(results_dir / "summary.md", report)


def load_optional_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_rows(path)


def write_progress(*, results_dir: Path) -> None:
    status_path = results_dir / "status.json"
    if not status_path.exists():
        raise SystemExit(f"Missing status file: {status_path}")
    status = json.loads(status_path.read_text())
    stamp = status["stamp"]
    jobs_dir = Path(status["jobs_dir"])
    formal_effort = formal_ceiling_effort(status, {})
    stages = {
        f"formal_ceiling_gpt55_{formal_effort}": stage_progress(
            status=status,
            stage_key=f"ceiling_{formal_effort}",
            fallback_job_names=[
                f"shallowswe_codex_sub_sizing_{stamp}_ceiling_gpt55_{formal_effort}_n1"
            ],
            jobs_dir=jobs_dir,
        ),
        "floor_gpt54mini_low": stage_progress(
            status=status,
            stage_key="floor_gpt54mini_low",
            fallback_job_names=[f"shallowswe_codex_sub_sizing_{stamp}_floor_gpt54mini_low_n3"],
            jobs_dir=jobs_dir,
        ),
    }
    for smoke_effort in ("medium", "high"):
        if f"ceiling_{smoke_effort}" not in status.get("stages", {}):
            continue
        stages[f"practical_smoke_gpt55_{smoke_effort}"] = stage_progress(
            status=status,
            stage_key=f"ceiling_{smoke_effort}",
            fallback_job_names=[
                f"shallowswe_codex_sub_sizing_{stamp}_ceiling_gpt55_{smoke_effort}_n1"
            ],
            jobs_dir=jobs_dir,
        )

    progress = {
        "schema_version": "shallowswe.codex_subscription_progress.v0.2",
        "results_dir": str(results_dir),
        "task_count": status["task_count"],
        "stages": stages,
    }
    write_json(results_dir / "progress.json", progress)


def stage_progress(
    *,
    status: dict[str, Any],
    stage_key: str,
    fallback_job_names: list[str],
    jobs_dir: Path,
) -> dict[str, Any]:
    stage = status.get("stages", {}).get(stage_key, {})
    job_names = stage.get("job_names")
    if not job_names and stage.get("job_name"):
        job_names = [stage["job_name"]]
    if not job_names:
        job_names = fallback_job_names
    return pier_jobs_progress([jobs_dir / job_name for job_name in job_names])


def pier_jobs_progress(job_dirs: list[Path]) -> dict[str, Any]:
    job_progresses = [(job_dir, pier_job_progress(job_dir)) for job_dir in job_dirs]
    existing = [
        (job_dir, progress)
        for job_dir, progress in job_progresses
        if progress["status"] != "not_started"
    ]
    not_started_job_dirs = [
        str(job_dir)
        for job_dir, progress in job_progresses
        if progress["status"] == "not_started"
    ]
    if not existing:
        return {"status": "not_started"}
    if len(existing) == 1 and not not_started_job_dirs:
        progress = dict(existing[0][1])
        if "job_dir" in progress:
            progress["job_dirs"] = [progress["job_dir"]]
        return progress

    completed_tasks = [
        row for _, progress in existing for row in progress.get("completed_tasks", [])
    ]
    active_or_pending = [
        name
        for _, progress in existing
        for name in progress.get("active_or_pending_trial_dirs", [])
    ]
    return {
        "status": "running" if active_or_pending or not_started_job_dirs else "complete",
        "job_dirs": [
            progress["job_dir"] for _, progress in existing if "job_dir" in progress
        ],
        "not_started_job_dirs": not_started_job_dirs,
        "trial_dirs": sum(int(progress.get("trial_dirs", 0)) for _, progress in existing),
        "completed": sum(int(progress.get("completed", 0)) for _, progress in existing),
        "passes": sum(int(progress.get("passes", 0)) for _, progress in existing),
        "failures": sum(int(progress.get("failures", 0)) for _, progress in existing),
        "exceptions": sum(int(progress.get("exceptions", 0)) for _, progress in existing),
        "active_or_pending_trial_dirs": active_or_pending,
        "completed_tasks": completed_tasks,
    }


def pier_job_progress(job_dir: Path) -> dict[str, Any]:
    if not job_dir.exists():
        return {"status": "not_started"}

    rows = []
    for path in sorted(job_dir.glob("*/result.json")):
        data = json.loads(path.read_text())
        reward = (data.get("verifier_result") or {}).get("rewards", {}).get("reward")
        exception = data.get("exception_info") or {}
        rows.append(
            {
                "task_id": data.get("task_name", "").split("/")[-1],
                "trial_name": data.get("trial_name"),
                "job_dir": str(job_dir),
                "passed": reward == 1.0,
                "reward": reward,
                "exception_type": exception.get("exception_type"),
                "started_at": data.get("started_at"),
                "finished_at": data.get("finished_at"),
            }
        )

    trial_dirs = sorted(path.name for path in job_dir.iterdir() if path.is_dir())
    completed_trials = {row["trial_name"] for row in rows}
    active_or_pending = [name for name in trial_dirs if name not in completed_trials]
    return {
        "status": "running" if active_or_pending else "complete",
        "job_dir": str(job_dir),
        "trial_dirs": len(trial_dirs),
        "completed": len(rows),
        "passes": sum(1 for row in rows if row["passed"]),
        "failures": sum(1 for row in rows if row["reward"] == 0.0),
        "exceptions": sum(1 for row in rows if row["exception_type"]),
        "active_or_pending_trial_dirs": active_or_pending,
        "completed_tasks": rows,
    }


def rollout_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored_rows = [row for row in rows if is_scored_row(row)]
    attempts = len(scored_rows)
    passes = sum(1 for row in scored_rows if row.get("passed"))
    excluded = len(rows) - attempts
    return {
        "total_rows": len(rows),
        "attempts": attempts,
        "passes": passes,
        "pass_rate": passes / attempts if attempts else None,
        "passed": passes > 0,
        "scored_failure": attempts > 0 and passes == 0,
        "excluded": excluded,
        "exceptions": excluded,
    }


def floor_attempts_per_task(status: dict[str, Any], floor_rows: list[dict[str, Any]]) -> int | None:
    floor_stage = status.get("stages", {}).get("floor_gpt54mini_low", {})
    if "attempts_per_task" in floor_stage:
        return int(floor_stage["attempts_per_task"])
    if not floor_rows:
        return None
    counts: dict[str, int] = defaultdict(int)
    for row in floor_rows:
        counts[row["task_id"]] += 1
    return max(counts.values()) if counts else None


def group_by_task(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["task_id"]].append(row)
    return grouped


def provisional_floor_size(pass_rate: float | None) -> str | None:
    if pass_rate is None:
        return None
    if pass_rate >= 0.70:
        return "small"
    if pass_rate >= 0.30:
        return "medium"
    return "large"


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_markdown_summary(path: Path, report: dict[str, Any]) -> None:
    tasks = report["tasks"]
    by_floor_size: dict[str, int] = defaultdict(int)
    by_formal_ceiling: dict[str, int] = defaultdict(int)
    for task in tasks:
        by_floor_size[str(task["provisional_floor_size"])] += 1
        ceiling_summary = task["codex_5_5_formal_ceiling"]
        ceiling_status = "pass" if ceiling_summary["passed"] else "fail"
        if not ceiling_summary["attempts"]:
            ceiling_status = (
                "excluded" if ceiling_summary["excluded"] else "pending"
            )
        by_formal_ceiling[ceiling_status] += 1

    formal = report["formal_ceiling"]

    lines = [
        "# Codex Subscription Sizing",
        "",
        f"Tasks: {len(tasks)}",
        "",
        "## Formal Ceiling",
        "",
        f"- Model config: `{formal['model_config']}`",
        "- Medium smoke rows, when present, are not formal ceiling evidence.",
        f"- Passed: {by_formal_ceiling.get('pass', 0)}",
        f"- Failed: {by_formal_ceiling.get('fail', 0)}",
        f"- Excluded: {by_formal_ceiling.get('excluded', 0)}",
        f"- Pending: {by_formal_ceiling.get('pending', 0)}",
        "",
        "## Provisional Floor Sizes",
        "",
        *[
            f"- `{size}`: {by_floor_size.get(size, 0)}"
            for size in ("small", "medium", "large", "None")
        ],
        "",
        "## Tasks",
        "",
        "| Task | Metadata | Floor Probe | Formal Ceiling | Medium Smoke |",
        "| --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        floor = floor_cell(task)
        ceiling = ceiling_cell(task["codex_5_5_formal_ceiling"])
        medium_smoke = ceiling_cell(task["codex_5_5_medium_smoke"])
        lines.append(
            "| "
            f"`{task['task_id']}` | "
            f"{task['metadata_size']} | "
            f"{floor} | "
            f"{ceiling} | "
            f"{medium_smoke} |"
        )
    path.write_text("\n".join(lines) + "\n")


def floor_cell(task: dict[str, Any]) -> str:
    attempts = task["codex_5_4_mini_low_attempts"]
    if attempts == 0:
        if task.get("codex_5_4_mini_low_excluded"):
            return f"excluded ({task['codex_5_4_mini_low_excluded']})"
        return "pending"
    return (
        f"{task['provisional_floor_size']} "
        f"({task['codex_5_4_mini_low_passes']}/{attempts})"
    )


def ceiling_cell(summary: dict[str, Any]) -> str:
    attempts = summary["attempts"]
    if attempts == 0:
        if summary.get("excluded"):
            return f"excluded ({summary['excluded']})"
        return "pending"
    return f"{summary['passes']}/{attempts}"


if __name__ == "__main__":
    sys.exit(main())

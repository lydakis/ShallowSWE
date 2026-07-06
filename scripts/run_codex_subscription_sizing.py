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
    all_task_ids = [row["task_id"] for row in task_metadata]

    status: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stamp": stamp,
        "task_count": len(all_task_ids),
        "jobs_dir": str(jobs_dir),
        "results_dir": str(results_dir),
        "stages": {},
    }
    write_json(results_dir / "status.json", status)

    ceiling_rows_by_effort: dict[str, list[dict[str, Any]]] = {}
    remaining = all_task_ids
    for effort in ("medium", "high", "xhigh"):
        if not remaining:
            status["stages"][f"ceiling_{effort}"] = {"status": "skipped", "task_count": 0}
            write_json(results_dir / "status.json", status)
            continue

        job_name = f"shallowswe_codex_sub_sizing_{stamp}_ceiling_gpt55_{effort}_n1"
        run_pier_job(
            tasks_root=tasks_root,
            jobs_dir=jobs_dir,
            job_name=job_name,
            model="openai/gpt-5.5",
            reasoning_effort=effort,
            attempts=1,
            task_ids=remaining,
            log_path=log_path,
            env=env,
            concurrency=args.concurrency,
        )
        rollouts_path = results_dir / f"ceiling-gpt55-{effort}-rollouts.json"
        export_pier_job(jobs_dir / job_name, tasks_root, rollouts_path, log_path, env)
        rows = load_rows(rollouts_path)
        ceiling_rows_by_effort[effort] = rows
        remaining = failed_task_ids(rows)

        status["stages"][f"ceiling_{effort}"] = {
            "status": "complete",
            "job_name": job_name,
            "rollouts": str(rollouts_path),
            "task_count": len({row["task_id"] for row in rows}),
            "failed_task_count": len(remaining),
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
    parser.add_argument("--concurrency", type=int, default=1)
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
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    return sorted(
        task_id
        for task_id, task_rows in by_task.items()
        if not any(bool(row.get("passed")) for row in task_rows)
    )


def build_report(
    *,
    task_metadata: list[dict[str, Any]],
    ceiling_rows_by_effort: dict[str, list[dict[str, Any]]],
    floor_rows: list[dict[str, Any]],
    status: dict[str, Any],
) -> dict[str, Any]:
    medium_by_task = group_by_task(ceiling_rows_by_effort.get("medium", []))
    diagnostic_by_effort = {
        effort: group_by_task(ceiling_rows_by_effort.get(effort, []))
        for effort in ("high", "xhigh")
    }
    floor_by_task = group_by_task(floor_rows)
    tasks = []
    for meta in task_metadata:
        task_id = meta["task_id"]
        medium_summary = rollout_summary(medium_by_task.get(task_id, []))
        diagnostic_summaries = {
            effort: rollout_summary(diagnostic_by_effort[effort].get(task_id, []))
            for effort in ("high", "xhigh")
        }
        diagnostic_rescue_effort = next(
            (
                effort
                for effort in ("high", "xhigh")
                if diagnostic_summaries[effort]["passed"]
            ),
            None,
        )

        floor_task_rows = floor_by_task.get(task_id, [])
        floor_passes = sum(1 for row in floor_task_rows if row.get("passed"))
        floor_attempts = len(floor_task_rows)
        floor_pass_rate = floor_passes / floor_attempts if floor_attempts else None
        tasks.append(
            {
                "task_id": task_id,
                "category": meta["category"],
                "metadata_size": meta["size"],
                "calibration_status": meta["calibration_status"],
                "codex_5_5_medium_ceiling": medium_summary,
                "codex_5_5_diagnostics": diagnostic_summaries,
                "codex_5_5_diagnostic_rescue_effort": diagnostic_rescue_effort,
                "codex_5_4_mini_low_attempts": floor_attempts,
                "codex_5_4_mini_low_passes": floor_passes,
                "codex_5_4_mini_low_pass_rate": floor_pass_rate,
                "provisional_floor_size": provisional_floor_size(floor_pass_rate),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "fixed_ceiling": {
            "model": "openai/gpt-5.5",
            "reasoning_effort": "medium",
            "role": "fixed ceiling calibration point",
            "rule": (
                "Only gpt-5.5 medium counts as the ceiling signal. High and xhigh "
                "runs are diagnostics for medium failures, not alternate ceilings."
            ),
        },
        "diagnostic_effort_ladder": {
            "model": "openai/gpt-5.5",
            "efforts": ["high", "xhigh"],
            "role": "diagnostic rescue signal only",
            "rule": "Run high only for medium failures and xhigh only for high failures.",
        },
        "floor_probe": {
            "model": "openai/gpt-5.4-mini",
            "reasoning_effort": "low",
            "attempts_per_task": floor_attempts_per_task(status, floor_rows),
            "size_rule": "N=3 provisional: >=0.70 small, >=0.30 medium, otherwise large.",
        },
        "tasks": tasks,
    }


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
    progress = {
        "schema_version": "shallowswe.codex_subscription_progress.v0.2",
        "results_dir": str(results_dir),
        "task_count": status["task_count"],
        "stages": {
            "fixed_ceiling_gpt55_medium": pier_job_progress(
                jobs_dir / f"shallowswe_codex_sub_sizing_{stamp}_ceiling_gpt55_medium_n1"
            ),
            "diagnostic_gpt55_high": pier_job_progress(
                jobs_dir / f"shallowswe_codex_sub_sizing_{stamp}_ceiling_gpt55_high_n1"
            ),
            "diagnostic_gpt55_xhigh": pier_job_progress(
                jobs_dir / f"shallowswe_codex_sub_sizing_{stamp}_ceiling_gpt55_xhigh_n1"
            ),
            "floor_gpt54mini_low": pier_job_progress(
                jobs_dir / f"shallowswe_codex_sub_sizing_{stamp}_floor_gpt54mini_low_n3"
            ),
        },
    }
    write_json(results_dir / "progress.json", progress)


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
    attempts = len(rows)
    passes = sum(1 for row in rows if row.get("passed"))
    exception_count = sum(1 for row in rows if row.get("exclusion_reason"))
    return {
        "attempts": attempts,
        "passes": passes,
        "pass_rate": passes / attempts if attempts else None,
        "passed": passes > 0,
        "exceptions": exception_count,
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
    by_medium_ceiling: dict[str, int] = defaultdict(int)
    by_diagnostic_rescue: dict[str, int] = defaultdict(int)
    for task in tasks:
        by_floor_size[str(task["provisional_floor_size"])] += 1
        medium_status = "pass" if task["codex_5_5_medium_ceiling"]["passed"] else "fail"
        if not task["codex_5_5_medium_ceiling"]["attempts"]:
            medium_status = "pending"
        by_medium_ceiling[medium_status] += 1
        by_diagnostic_rescue[str(task["codex_5_5_diagnostic_rescue_effort"])] += 1

    lines = [
        "# Codex Subscription Sizing",
        "",
        f"Tasks: {len(tasks)}",
        "",
        "## Fixed Ceiling",
        "",
        "- Model config: `openai/gpt-5.5[medium]`",
        f"- Passed: {by_medium_ceiling.get('pass', 0)}",
        f"- Failed: {by_medium_ceiling.get('fail', 0)}",
        f"- Pending: {by_medium_ceiling.get('pending', 0)}",
        "",
        "## Diagnostic Effort Ladder",
        "",
        "- High/xhigh are diagnostic rescue runs for medium failures only.",
        f"- Rescued by `high`: {by_diagnostic_rescue.get('high', 0)}",
        f"- Rescued by `xhigh`: {by_diagnostic_rescue.get('xhigh', 0)}",
        f"- Not rescued or not run: {by_diagnostic_rescue.get('None', 0)}",
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
        "| Task | Metadata | Floor Probe | 5.5 Medium Ceiling | Diagnostic Rescue |",
        "| --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        floor = floor_cell(task)
        ceiling = ceiling_cell(task["codex_5_5_medium_ceiling"])
        lines.append(
            "| "
            f"`{task['task_id']}` | "
            f"{task['metadata_size']} | "
            f"{floor} | "
            f"{ceiling} | "
            f"{task['codex_5_5_diagnostic_rescue_effort']} |"
        )
    path.write_text("\n".join(lines) + "\n")


def floor_cell(task: dict[str, Any]) -> str:
    attempts = task["codex_5_4_mini_low_attempts"]
    if attempts == 0:
        return "pending"
    return (
        f"{task['provisional_floor_size']} "
        f"({task['codex_5_4_mini_low_passes']}/{attempts})"
    )


def ceiling_cell(summary: dict[str, Any]) -> str:
    attempts = summary["attempts"]
    if attempts == 0:
        return "pending"
    return f"{summary['passes']}/{attempts}"


if __name__ == "__main__":
    sys.exit(main())

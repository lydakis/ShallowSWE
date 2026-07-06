from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = "shallowswe.failed_trajectory_audit.v0.1"


def main() -> int:
    args = parse_args()
    results_dir = args.results_dir.resolve()
    tasks_root = args.tasks_root.resolve()
    progress = json.loads((results_dir / "progress.json").read_text())

    failed_trajectories = collect_failed_trajectories(progress)
    failed_task_ids = sorted({row["task_id"] for row in failed_trajectories})
    task_audits = {
        task_id: audit_task(tasks_root / task_id, args.solution_timeout_sec)
        for task_id in failed_task_ids
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "results_dir": str(results_dir),
        "failed_trajectory_count": len(failed_trajectories),
        "failed_task_count": len(failed_task_ids),
        "failed_trajectories": failed_trajectories,
        "tasks": task_audits,
        "summary": summarize(failed_trajectories, task_audits),
    }

    output_json = results_dir / "failed-trajectory-audit.json"
    output_md = results_dir / "failed-trajectory-audit.md"
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    output_md.write_text(markdown_report(report) + "\n")
    print(output_json)
    print(output_md)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit failed Pier trajectories and task verifiers.")
    parser.add_argument("results_dir", type=Path)
    parser.add_argument("--tasks-root", type=Path, default=Path("tasks"))
    parser.add_argument("--solution-timeout-sec", type=int, default=180)
    return parser.parse_args()


def collect_failed_trajectories(progress: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_name, stage in sorted(progress.get("stages", {}).items()):
        job_dir = Path(stage.get("job_dir", ""))
        for row in stage.get("completed_tasks", []):
            if row.get("passed") or row.get("reward") != 0.0:
                continue
            trial_dir = job_dir / str(row["trial_name"])
            result = read_json(trial_dir / "result.json")
            verifier_stdout = read_text(trial_dir / "verifier" / "test-stdout.txt")
            reward_text = read_text(trial_dir / "verifier" / "reward.txt").strip()
            rows.append(
                {
                    "stage": stage_name,
                    "task_id": row["task_id"],
                    "trial_name": row["trial_name"],
                    "trial_dir": str(trial_dir),
                    "reward": row.get("reward"),
                    "exception_type": row.get("exception_type"),
                    "started_at": row.get("started_at"),
                    "finished_at": row.get("finished_at"),
                    "result_exception": (result.get("exception_info") or {}).get("exception_type"),
                    "verifier_reward_txt": reward_text,
                    "verifier_stdout_tail": tail(verifier_stdout, 20),
                    "failure_signature": failure_signature(verifier_stdout),
                }
            )
    return rows


def audit_task(task_dir: Path, timeout_sec: int) -> dict[str, Any]:
    image = build_task_image(task_dir, timeout_sec)
    solution_results = []
    for solution_dir in sorted(task_dir.glob("solution*")):
        if not solution_dir.is_dir():
            continue
        solve = solution_dir / "solve.sh"
        if not solve.exists():
            continue
        result = run_solution_check(task_dir, solution_dir, image, timeout_sec)
        solution_results.append(result)
        if result["verifier_passed"]:
            break

    any_solution_passed = any(row["verifier_passed"] for row in solution_results)
    return {
        "instruction_path": str(task_dir / "instruction.md"),
        "verifier_path": str(task_dir / "tests" / "test.sh"),
        "solution_checks": solution_results,
        "official_solution_passed": any_solution_passed,
        "verdict": "verifier_sanity_passed" if any_solution_passed else "needs_human_review",
    }


def build_task_image(task_dir: Path, timeout_sec: int) -> str:
    build = subprocess.run(
        ["docker", "build", "-q", str(task_dir / "environment")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=max(timeout_sec, 120),
        check=False,
    )
    image = next((line.strip() for line in reversed(build.stdout.splitlines()) if line.strip()), "")
    if build.returncode != 0 or not image:
        raise RuntimeError(
            f"failed to build task image for {task_dir.name}: {tail(build.stdout, 20)}"
        )
    return image


def run_solution_check(
    task_dir: Path,
    solution_dir: Path,
    image: str,
    timeout_sec: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="shallowswe-audit-") as tmp_name:
        tmp = Path(tmp_name)
        log_dir = tmp / "verifier"
        log_dir.mkdir()
        container_name = f"shallowswe-audit-{uuid4().hex}"
        command = (
            "bash /solution/solve.sh; "
            "solution_status=$?; "
            "echo __SOLUTION_EXIT__=$solution_status; "
            "if [ $solution_status -eq 0 ]; then "
            "  bash /task-tests/test.sh; verifier_status=$?; "
            "else "
            "  verifier_status=99; "
            "fi; "
            "echo __VERIFIER_EXIT__=$verifier_status; "
            "exit $verifier_status"
        )
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "-v",
            f"{solution_dir}:/solution:ro",
            "-v",
            f"{task_dir / 'tests'}:/task-tests:ro",
            "-v",
            f"{log_dir}:/logs/verifier",
            image,
            "bash",
            "-lc",
            command,
        ]
        try:
            run = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            output = run.stdout
            timed_out = False
            return_code = run.returncode
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            timed_out = True
            return_code = 124
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        reward = read_text(log_dir / "reward.txt").strip()
        solution_exit_code = tagged_exit_code(output, "__SOLUTION_EXIT__", return_code)
        verifier_exit_code = tagged_exit_code(output, "__VERIFIER_EXIT__", return_code)
        return {
            "solution": solution_dir.name,
            "timed_out": timed_out,
            "solution_exit_code": solution_exit_code,
            "verifier_exit_code": verifier_exit_code,
            "verifier_reward_txt": reward,
            "verifier_passed": verifier_exit_code == 0 and reward == "1",
            "output_tail": tail(output, 30),
        }


def tagged_exit_code(text: str, tag: str, default: int = -1) -> int:
    prefix = f"{tag}="
    for line in reversed(text.splitlines()):
        if line.startswith(prefix):
            try:
                return int(line.removeprefix(prefix))
            except ValueError:
                return default
    return default


def summarize(
    failed_trajectories: list[dict[str, Any]],
    task_audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_stage: dict[str, int] = defaultdict(int)
    by_task: dict[str, int] = defaultdict(int)
    for row in failed_trajectories:
        by_stage[row["stage"]] += 1
        by_task[row["task_id"]] += 1
    return {
        "failed_by_stage": dict(sorted(by_stage.items())),
        "failed_by_task": dict(sorted(by_task.items())),
        "tasks_with_solution_sanity_pass": sorted(
            task_id
            for task_id, audit in task_audits.items()
            if audit["official_solution_passed"]
        ),
        "tasks_needing_human_review": sorted(
            task_id
            for task_id, audit in task_audits.items()
            if not audit["official_solution_passed"]
        ),
    }


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Failed Trajectory Audit",
        "",
        f"Failed trajectories audited: {report['failed_trajectory_count']}",
        f"Unique failed tasks: {report['failed_task_count']}",
        "",
        "## Stage Counts",
        "",
    ]
    for stage, count in summary["failed_by_stage"].items():
        lines.append(f"- `{stage}`: {count}")
    lines.extend(["", "## Task Verifier Sanity", ""])
    for task_id, audit in sorted(report["tasks"].items()):
        status = "pass" if audit["official_solution_passed"] else "needs review"
        checks = ", ".join(
            f"{row['solution']}={row['verifier_reward_txt'] or row['verifier_exit_code']}"
            for row in audit["solution_checks"]
        )
        lines.append(f"- `{task_id}`: {status}; {checks}")
    lines.extend(["", "## Failed Trajectories", ""])
    for row in report["failed_trajectories"]:
        signature = row["failure_signature"] or "no verifier stdout"
        lines.append(
            f"- `{row['stage']}` `{row['task_id']}` `{row['trial_name']}`: {signature}"
        )
    return "\n".join(lines)


def failure_signature(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        if "AssertionError" in line:
            return line
    return lines[-1]


def tail(text: str, line_count: int) -> list[str]:
    if not text:
        return []
    return text.splitlines()[-line_count:]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())

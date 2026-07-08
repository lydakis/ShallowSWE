from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time
from typing import Any


def main() -> int:
    args = parse_args()
    last_signature = ""

    while tmux_session_exists(args.main_session):
        signature = refresh_and_maybe_audit(args, last_signature)
        if signature is not None:
            last_signature = signature
        time.sleep(args.interval_sec)

    refresh_and_maybe_audit(args, "", force=True)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh progress and rerun failed-trajectory audit when failures change."
    )
    parser.add_argument("results_dir", type=Path)
    parser.add_argument("--tasks-root", type=Path, default=Path("tasks"))
    parser.add_argument("--main-session", default="shallowswe_codex_sizing_20260706")
    parser.add_argument("--interval-sec", type=int, default=120)
    return parser.parse_args()


def refresh_and_maybe_audit(
    args: argparse.Namespace,
    last_signature: str,
    *,
    force: bool = False,
) -> str | None:
    run(
        [
            "uv",
            "run",
            "python",
            "scripts/run_codex_subscription_sizing.py",
            "--progress-only",
            str(args.results_dir),
        ]
    )
    progress = json.loads((args.results_dir / "progress.json").read_text())
    signature, failed_count = failed_signature(progress)
    if not force and signature == last_signature:
        log(f"no new failed trajectory signature; failed_count={failed_count}")
        return None

    log(f"auditing failed trajectories; failed_count={failed_count}")
    run(
        [
            "uv",
            "run",
            "python",
            "scripts/audit_failed_trajectories.py",
            str(args.results_dir),
            "--tasks-root",
            str(args.tasks_root),
        ]
    )
    review_json = args.results_dir / "failed-trajectory-validity-review.json"
    audit_json = args.results_dir / "failed-trajectory-audit.json"
    if review_json.exists():
        completed = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/check_failed_validity_review.py",
                str(audit_json),
                str(review_json),
            ],
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            log("qualitative validity review is missing coverage for new failed tasks")
    return signature


def failed_signature(progress: dict[str, Any]) -> tuple[str, int]:
    failed = []
    for stage_name, stage in sorted(progress.get("stages", {}).items()):
        for row in stage.get("completed_tasks", []):
            if row.get("passed") or row.get("reward") != 0.0:
                continue
            failed.append(
                {
                    "stage": stage_name,
                    "task_id": row.get("task_id"),
                    "trial_name": row.get("trial_name"),
                }
            )
    payload = json.dumps(sorted(failed, key=lambda row: tuple(row.values())), sort_keys=True)
    return sha256(payload.encode()).hexdigest(), len(failed)


def tmux_session_exists(name: str) -> bool:
    return (
        subprocess.run(
            ["tmux", "has-session", "-t", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def run(cmd: list[str]) -> None:
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, text=True, check=True)


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {message}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

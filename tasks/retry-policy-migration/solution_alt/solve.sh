#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "retry_parser" / "scheduler.py"
path.write_text(
    '''from __future__ import annotations

from retry_parser.parser import parse_retry_row


def _fixed_shape(parsed: dict[str, object]) -> dict[str, object]:
    return {
        "job_id": parsed["job_id"],
        "attempts": parsed["attempts"],
        "delay_seconds": parsed["delay_seconds"],
        "mode": parsed["mode"],
    }


def build_retry_plan(row: dict[str, str]) -> dict[str, object]:
    parsed = parse_retry_row(row)
    if "max_attempts" not in parsed:
        return _fixed_shape(parsed)

    attempts = int(parsed["attempts"])
    maximum = int(parsed["max_attempts"])
    if parsed.get("status") == "done" or attempts >= maximum or not bool(parsed.get("retryable")):
        return _fixed_shape(parsed)

    delay = int(parsed["delay_seconds"])
    schedule: list[int] = []
    next_delay = delay
    for _ in range(attempts + 1, maximum + 1):
        schedule.append(min(next_delay, 3600))
        next_delay *= 2

    return {
        "job_id": parsed["job_id"],
        "attempts": attempts,
        "delay_seconds": delay,
        "max_attempts": maximum,
        "mode": parsed["mode"],
        "retry_schedule_seconds": schedule,
    }
'''
)
PY

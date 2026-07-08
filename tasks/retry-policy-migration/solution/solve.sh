#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

app = Path(os.environ.get("APP_DIR", "/app"))
(app / "retry_parser" / "scheduler.py").write_text(
    '''from __future__ import annotations

from retry_parser.parser import parse_retry_row


LEGACY_KEYS = ("job_id", "attempts", "delay_seconds", "mode")
ELIGIBLE_KEYS = ("job_id", "attempts", "delay_seconds", "max_attempts", "mode")


def _legacy(parsed: dict[str, object]) -> dict[str, object]:
    return {key: parsed[key] for key in LEGACY_KEYS}


def _schedule(delay_seconds: int, attempts: int, max_attempts: int) -> list[int]:
    return [min(delay_seconds * (2 ** offset), 3600) for offset in range(max_attempts - attempts)]


def build_retry_plan(row: dict[str, str]) -> dict[str, object]:
    parsed = parse_retry_row(row)
    if "max_attempts" not in parsed:
        return _legacy(parsed)
    attempts = int(parsed["attempts"])
    max_attempts = int(parsed["max_attempts"])
    if not parsed.get("retryable") or parsed.get("status") == "done" or attempts >= max_attempts:
        return _legacy(parsed)
    plan = {key: parsed[key] for key in ELIGIBLE_KEYS}
    plan["retry_schedule_seconds"] = _schedule(int(parsed["delay_seconds"]), attempts, max_attempts)
    return plan
'''
)
PY

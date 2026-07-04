#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "retry_parser" / "parser.py"
path.write_text(
    """FALLBACK_ATTEMPTS = 0
FALLBACK_DELAY_SECONDS = 30


def _fallback(row):
    return {
        "job_id": row.get("job_id", ""),
        "attempts": FALLBACK_ATTEMPTS,
        "delay_seconds": FALLBACK_DELAY_SECONDS,
        "mode": "fallback",
    }


def parse_retry_row(row):
    try:
        attempts = int(row["attempts"])
        delay_seconds = int(row["delay_seconds"])
    except (KeyError, TypeError, ValueError):
        return _fallback(row)

    return {
        "job_id": row["job_id"],
        "attempts": attempts,
        "delay_seconds": delay_seconds,
        "mode": row.get("mode") or "standard",
    }
"""
)
PY

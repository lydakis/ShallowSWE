#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "auth_tokens" / "tokens.py"
path.write_text(
    """from datetime import datetime, timezone


MILLISECONDS_CUTOFF = 10_000_000_000


def expires_at_seconds(token):
    expires_at = float(token["expires_at"])
    if expires_at > MILLISECONDS_CUTOFF:
        return expires_at / 1000
    return expires_at


def is_expired(token, now=None):
    current = now or datetime.now(timezone.utc)
    return expires_at_seconds(token) <= current.timestamp()


def can_login(token, now=None):
    return bool(token.get("user_id")) and not is_expired(token, now)
"""
)
PY

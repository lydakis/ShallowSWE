#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "app" / "alerts.py"
path.write_text(
    """import vendor_notifier


def send_alert(user_id, subject, body):
    payload = {"user_id": user_id, "subject": subject, "body": body}
    return vendor_notifier.send_message(**payload)
"""
)
PY

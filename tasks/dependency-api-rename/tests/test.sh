#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os, sys
app = Path(os.environ.get("APP_DIR", "/app")); sys.path.insert(0, str(app))
from app.alerts import send_alert
result = send_alert("U-1", "Deploy failed", "Unit tests failed")
assert result == {"user_id": "U-1", "subject": "Deploy failed", "body": "Unit tests failed", "transport": "v2"}
assert "notify_user" not in (app / "app" / "alerts.py").read_text()
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import os, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from auth_tokens.tokens import can_login, is_expired
now=datetime(2026,7,4,12,0,tzinfo=timezone.utc)
assert can_login({"user_id":"U-1","expires_at":1783195200000}, now)
assert not can_login({"user_id":"U-2","expires_at":1700000000000}, now)
assert can_login({"user_id":"U-3","expires_at":1783195200}, now)
assert is_expired({"user_id":"U-4","expires_at":int(now.timestamp())-1}, now)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

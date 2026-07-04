#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os, sys
app = Path(os.environ.get("APP_DIR", "/app")); sys.path.insert(0, str(app))
from profile_tools import app as profile_app
from profile_tools import helpers
assert helpers.format_user_id(" Ada Lovelace ") == "ada-lovelace"
assert helpers.format_user_id("Grace Hopper") == "grace-hopper"
assert not hasattr(helpers, "format_user_key")
assert profile_app.describe_user("Katherine Johnson") == "user:katherine-johnson"
assert "format_user_key" not in (app / "profile_tools" / "app.py").read_text()
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

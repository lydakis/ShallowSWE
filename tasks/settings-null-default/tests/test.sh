#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import json, os, subprocess, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from settings_app.config import load_settings
assert load_settings(app/"settings.full.json") == {"theme":"dark","notifications":{"email":True,"sms":False}}
assert load_settings(app/"settings.missing.json") == {"theme":"light","notifications":{"email":False,"sms":False}}
partial=app/"partial.json"; partial.write_text('{"notifications":{"email":true}}')
assert load_settings(partial)["notifications"] == {"email": True, "sms": False}
result=subprocess.run([sys.executable,"-m","settings_app.cli",str(app/"settings.missing.json")],cwd=app,text=True,stdout=subprocess.PIPE,check=True)
assert json.loads(result.stdout)["notifications"] == {"email": False, "sms": False}
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import json, os, subprocess, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from retry_parser.parser import parse_retry_row
assert parse_retry_row({"job_id":"ok","attempts":"2","delay_seconds":"10"}) == {"job_id":"ok","attempts":2,"delay_seconds":10,"mode":"standard"}
assert parse_retry_row({"job_id":"bad","attempts":"oops","delay_seconds":"10"}) == {"job_id":"bad","attempts":0,"delay_seconds":30,"mode":"fallback"}
result=subprocess.run([sys.executable,"-m","retry_parser.cli",str(app/"retries.csv")],cwd=app,text=True,stdout=subprocess.PIPE,check=True)
rows=[json.loads(line) for line in result.stdout.splitlines()]
assert len(rows) == 4 and rows[2]["mode"] == "fallback" and rows[3]["delay_seconds"] == 30
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

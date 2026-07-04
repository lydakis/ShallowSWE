#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import csv, io, json, os, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from user_export.exporter import build_rows, render_csv
users=json.loads((app/"users.json").read_text()); rows=build_rows(users)
assert rows[0]["name"] == rows[0]["display_name"] == "Ada Lovelace"
assert list(rows[0]) == ["id","email","name","display_name"]
csv_rows=list(csv.DictReader(io.StringIO(render_csv(users))))
assert csv_rows[1]["name"] == "Grace Hopper" and csv_rows[1]["display_name"] == "Grace Hopper"
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

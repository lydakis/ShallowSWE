#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from datetime import date
from pathlib import Path
import os, subprocess, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from date_window.events import filter_events, load_events
events=load_events(app/"events.csv")
assert [e.event_id for e in filter_events(events,date(2026,7,1),date(2026,7,3))] == ["EV-1","EV-2","EV-3"]
assert [e.event_id for e in filter_events(events,date(2026,7,2),date(2026,7,2))] == ["EV-2"]
result=subprocess.run([sys.executable,"-m","date_window.cli",str(app/"events.csv"),"--start-date","2026-07-02","--end-date","2026-07-03"],cwd=app,text=True,stdout=subprocess.PIPE,check=True)
assert result.stdout.splitlines() == ["EV-2","EV-3"]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
assert (app/"notifications/text.py").exists() and (app/"notifications/html.py").exists()
from notifications.text import render_text
from notifications.html import render_html
from notifications.renderer import render_text as old_text, render_html as old_html
n={"severity":"warning","title":"Queue lag","body":"Workers are 8 minutes behind"}
assert render_text(n) == old_text(n) == "[WARNING] Queue lag: Workers are 8 minutes behind"
assert "<h1>Queue lag</h1>" in render_html(n) and render_html(n) == old_html(n)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

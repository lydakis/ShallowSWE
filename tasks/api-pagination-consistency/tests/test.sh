#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from catalog_api.items import list_items, summarize_page
items=[{"id":f"I-{i}"} for i in range(1,6)]
assert [i["id"] for i in list_items(items, page=2, per_page=2)] == ["I-3","I-4"]
assert [i["id"] for i in list_items(items, page=3, per_page=2)] == ["I-5"]
assert summarize_page(items) == {"count":5,"ids":["I-1","I-2","I-3","I-4","I-5"]}
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

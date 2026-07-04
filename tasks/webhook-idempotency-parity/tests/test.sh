#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os, sys
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from webhook_sync.events import apply_import, apply_webhook, initial_state, replay_events
events=[{"event_id":"evt-1","order_id":"ORD-1","amount_cents":1200,"status":"paid"},{"event_id":"evt-2","order_id":"ORD-2","amount_cents":500,"status":"paid"},{"event_id":"evt-1","order_id":"ORD-1","amount_cents":1200,"status":"paid"}]
assert apply_import(events, initial_state())["total_cents"] == 1700
s=initial_state(); apply_webhook(events[0], s); apply_webhook(events[0], s); assert s["processed_event_ids"] == ["evt-1"] and s["total_cents"] == 1200
s=replay_events(events+events, initial_state()); assert s["processed_event_ids"] == ["evt-1","evt-2"] and s["total_cents"] == 1700
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

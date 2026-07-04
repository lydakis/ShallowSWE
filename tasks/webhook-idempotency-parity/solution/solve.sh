#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"webhook_sync/events.py": "def initial_state(): return {\\"processed_event_ids\\": [], \\"total_cents\\": 0, \\"orders\\": {}}\\ndef _apply(event, state):\\n    processed=state.setdefault(\\"processed_event_ids\\", [])\\n    if event[\\"event_id\\"] in processed: return state\\n    processed.append(event[\\"event_id\\"]); state[\\"total_cents\\"] += event[\\"amount_cents\\"]; state[\\"orders\\"][event[\\"order_id\\"]]=event[\\"status\\"]; return state\\ndef apply_import(events, state):\\n    for event in events: _apply(event, state)\\n    return state\\ndef apply_webhook(event, state): return _apply(event, state)\\ndef replay_events(events, state):\\n    for event in events: _apply(event, state)\\n    return state\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

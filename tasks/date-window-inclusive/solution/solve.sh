#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"date_window/events.py": "from __future__ import annotations\\nfrom dataclasses import dataclass\\nfrom datetime import date\\nimport csv\\nfrom pathlib import Path\\n@dataclass(frozen=True)\\nclass Event:\\n    event_id: str\\n    occurred_on: date\\n    kind: str\\ndef load_events(path: str | Path) -> list[Event]:\\n    with Path(path).open(newline=\\"\\") as handle:\\n        return [Event(row[\\"event_id\\"], date.fromisoformat(row[\\"occurred_on\\"]), row[\\"kind\\"]) for row in csv.DictReader(handle)]\\ndef filter_events(events: list[Event], start_date: date, end_date: date) -> list[Event]:\\n    return [event for event in events if start_date <= event.occurred_on <= end_date]\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

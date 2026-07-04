#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "date_window" / "events.py"
text = path.read_text()
old = "start_date <= event.occurred_on < end_date"
new = "start_date <= event.occurred_on <= end_date"
if old not in text:
    raise SystemExit(f"expected exclusive end-date comparator not found in {path}")
path.write_text(text.replace(old, new, 1))
PY

#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "build_outputs.py"
text = path.read_text()
old = 'severity = "high" if status_int >= 500 else "medium" if status_int == 429 else ""'
new = 'severity = "high" if status_int in {500, 502, 503} else "medium" if status_int == 429 else ""'
if old not in text:
    raise SystemExit("expected severity classifier not found")
path.write_text(text.replace(old, new, 1))
PY

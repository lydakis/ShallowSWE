#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "build_outputs.py"
text = path.read_text()
old = '    incidents.sort(key=lambda row: row["timestamp"])\n'
if old not in text:
    raise SystemExit("expected incident sort not found")
path.write_text(text.replace(old, "", 1))
PY

#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "build_outputs.py"
text = path.read_text()
old = 'lowered = value.lower()\n    if lowered in {"true", "false"}:\n        return lowered == "true"'
new = 'if value in {"true", "false"}:\n        return value == "true"'
if old not in text:
    raise SystemExit("expected boolean coercion not found")
path.write_text(text.replace(old, new, 1))
PY

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

app = Path(os.environ.get("APP_DIR", "/app"))
for rel in ("profile_tools/app.py", "profile_tools/helpers.py"):
    path = app / rel
    path.write_text(path.read_text().replace("format_user_key", "format_user_id"))
PY

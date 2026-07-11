#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "apply_task.py"
text = path.read_text()
old = 'merged["features"].update(feature.get("features", {}))'
new = 'merged["features"]["enable_new_checkout"] = feature["features"]["enable_new_checkout"]'
path.write_text(text.replace(old, new, 1))
PY

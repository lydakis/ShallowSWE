#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "dispatch_app" / "config.py"
text = path.read_text()
start = 'include_archived=(\n            _truthy(values.get("DISPATCH_INCLUDE_ARCHIVED"))\n            or _truthy(values.get("DISPATCH_INCLUDE_CLOSED"))\n        ),'
path.write_text(text.replace(start, 'include_archived=True,', 1))
PY

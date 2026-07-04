#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "dispatch_app" / "config.py"
text = path.read_text()
text = text.replace(
    'include_archived=_truthy(values.get("DISPATCH_INCLUDE_CLOSED")),',
    'include_archived=any(\n'
    '            _truthy(values.get(key))\n'
    '            for key in ("DISPATCH_INCLUDE_ARCHIVED", "DISPATCH_INCLUDE_CLOSED")\n'
    '        ),',
)
path.write_text(text)
PY

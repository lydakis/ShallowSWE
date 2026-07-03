#!/usr/bin/env bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path

path = Path("dispatch_app/config.py")
text = path.read_text()
text = text.replace(
    'include_archived=_truthy(values.get("DISPATCH_INCLUDE_CLOSED")),',
    'include_archived=(\n'
    '            _truthy(values.get("DISPATCH_INCLUDE_ARCHIVED"))\n'
    '            or _truthy(values.get("DISPATCH_INCLUDE_CLOSED"))\n'
    '        ),',
)
path.write_text(text)
PY

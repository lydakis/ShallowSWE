#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "fulfillment_status" / "statuses.py"
text = path.read_text()
old = '''    if status not in known_statuses():
        raise StatusError(f"unknown status: {raw_status}")
    return status'''
new = '    return status'
path.write_text(text.replace(old, new, 1))
PY

#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_merge" / "importer.py"
text = path.read_text()
old = '''    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None'''
new = '''    parts = text.split("-")
    return text if len(parts) == 3 and all(part.isdigit() for part in parts) else None'''
path.write_text(text.replace(old, new, 1))
PY

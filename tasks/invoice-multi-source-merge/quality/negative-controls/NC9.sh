#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_merge" / "importer.py"
text = path.read_text().replace(
    'return str(value or "").strip().upper()',
    'return str(value or "").strip()',
    1,
)
path.write_text(text)
PY

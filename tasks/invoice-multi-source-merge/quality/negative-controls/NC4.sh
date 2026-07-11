#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_merge" / "importer.py"
text = path.read_text().replace(
    'REJECT_ORDER = {"api": 0, "csv": 1, "legacy": 2}',
    'REJECT_ORDER = {"legacy": 0, "csv": 1, "api": 2}',
)
path.write_text(text)
PY

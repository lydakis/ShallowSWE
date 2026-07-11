#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "fulfillment_status" / "statuses.py"
text = path.read_text().replace(
    'SUCCESSFUL_STATUSES = {"delivered"}',
    'SUCCESSFUL_STATUSES = {"delivered", "return_to_sender"}',
)
path.write_text(text)
PY

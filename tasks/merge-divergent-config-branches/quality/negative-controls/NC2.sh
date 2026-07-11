#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "apply_task.py"
text = path.read_text()
old = 'merged["retry_timeout_seconds"] = release["retry_timeout_seconds"]'
new = 'merged["retry_timeout_seconds"] = max(main["retry_timeout_seconds"], release["retry_timeout_seconds"], feature["retry_timeout_seconds"])'
path.write_text(text.replace(old, new, 1))
PY

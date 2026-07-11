#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"
cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from pathlib import Path
import json

output = Path.cwd() / "output" / "flags.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({
    "FEATURE_SEARCH": True,
    "MAX_RETRIES": 3,
    "SERVICE_NAME": "worker",
    "TIMEOUT_SECONDS": 1.5,
}, sort_keys=True))
PY

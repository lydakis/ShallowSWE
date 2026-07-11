#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"
cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from pathlib import Path
import json

root = Path.cwd()
values = {}
for raw_line in (root / "input" / "flags.env").read_text().splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = (part.strip() for part in line.split("=", 1))
    if key and value:
        values[key] = value
output = root / "output" / "flags.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(values))
PY

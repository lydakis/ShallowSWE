#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "apply_task.py"
text = path.read_text()
old = 'merged = merge_configs(main, release, feature)'
new = '''merged = {
        "region": release["region"],
        "retry_timeout_seconds": release["retry_timeout_seconds"],
        "features": dict(feature.get("features", {})),
    }'''
if old not in text:
    raise SystemExit("expected merge call not found")
path.write_text(text.replace(old, new, 1))
PY

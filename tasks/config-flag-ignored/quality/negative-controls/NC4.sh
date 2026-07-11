#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "dispatch_app" / "config.py"
text = path.read_text()
old = '''include_archived=(
            _truthy(values.get("DISPATCH_INCLUDE_ARCHIVED"))
            or _truthy(values.get("DISPATCH_INCLUDE_CLOSED"))
        ),'''
new = '''include_archived=(
            env_file is not None
            and Path(env_file).name == ".env.nightly"
            and _truthy(values.get("DISPATCH_INCLUDE_ARCHIVED"))
        ),'''
if old not in text:
    raise SystemExit("expected flag expression not found")
path.write_text(text.replace(old, new, 1))
PY

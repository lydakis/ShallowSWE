#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"profile_tools/app.py": "from .helpers import format_user_id\\n\\ndef describe_user(raw):\\n    return f\\"user:{format_user_id(raw)}\\"\\n", "profile_tools/helpers.py": "def format_user_id(raw):\\n    return raw.strip().lower().replace(\\" \\", \\"-\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"auth_tokens/tokens.py": "from datetime import datetime, timezone\\ndef _seconds(value):\\n    value = float(value)\\n    return value / 1000.0 if value > 10_000_000_000 else value\\ndef is_expired(token, now=None):\\n    current = now or datetime.now(timezone.utc)\\n    return _seconds(token[\\"expires_at\\"]) <= current.timestamp()\\ndef can_login(token, now=None): return bool(token.get(\\"user_id\\")) and not is_expired(token, now)\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

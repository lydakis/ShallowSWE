#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"settings_app/config.py": "from __future__ import annotations\\nimport json\\nfrom pathlib import Path\\ndef load_settings(path: str | Path) -> dict[str, object]:\\n    data = json.loads(Path(path).read_text())\\n    notifications = data.get(\\"notifications\\") or {}\\n    return {\\"theme\\": data.get(\\"theme\\", \\"light\\"), \\"notifications\\": {\\"email\\": bool(notifications.get(\\"email\\", False)), \\"sms\\": bool(notifications.get(\\"sms\\", False))}}\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

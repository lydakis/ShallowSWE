#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "settings_app" / "config.py"
text = path.read_text()
old = (
    '    notifications = data["notifications"]\n'
    '    return {"theme": data.get("theme", "light"), "notifications": '
    '{"email": bool(notifications["email"]), "sms": bool(notifications["sms"])}}\n'
)
new = (
    '    notifications = data.get("notifications") or {}\n'
    '    return {"theme": data.get("theme", "light"), "notifications": '
    '{"email": bool(notifications.get("email", False)), '
    '"sms": bool(notifications.get("sms", False))}}\n'
)
if old not in text:
    raise SystemExit(f"expected brittle notification lookup not found in {path}")
path.write_text(text.replace(old, new, 1))
PY

#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
cat > "$APP_DIR/settings_cache/cache.py" <<'PY'
_FIRST = None

def get_feature_flags(path):
    global _FIRST
    if _FIRST is None:
        import json
        _FIRST = json.loads(path.read_text())
    return dict(_FIRST)
PY

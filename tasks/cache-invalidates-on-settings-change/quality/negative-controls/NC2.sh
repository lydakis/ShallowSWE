#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
cat > "$APP_DIR/settings_cache/cache.py" <<'PY'
import json

_CACHE = None

def get_feature_flags(path):
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(path.read_text())
    return dict(_CACHE)
PY

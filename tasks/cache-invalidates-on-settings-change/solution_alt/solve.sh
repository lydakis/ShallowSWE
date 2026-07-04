#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/settings_cache/cache.py" <<'PY'
from __future__ import annotations

from pathlib import Path
import json


_CACHE: dict[str, tuple[str, dict[str, bool]]] = {}


def get_feature_flags(path):
    resolved = Path(path).resolve()
    raw = resolved.read_text()
    cache_key = str(resolved)
    cached = _CACHE.get(cache_key)
    if cached is None or cached[0] != raw:
        _CACHE[cache_key] = (raw, json.loads(raw))
    return dict(_CACHE[cache_key][1])
PY

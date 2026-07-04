#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"settings_cache/cache.py": "import json\\nfrom pathlib import Path\\n_CACHE = {}\\ndef get_feature_flags(path):\\n    resolved=Path(path).resolve(); content=resolved.read_text(); key=str(resolved)\\n    if key not in _CACHE or _CACHE[key][0] != content: _CACHE[key]=(content, json.loads(content))\\n    return dict(_CACHE[key][1])\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

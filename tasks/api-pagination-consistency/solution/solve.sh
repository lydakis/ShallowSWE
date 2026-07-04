#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"catalog_api/items.py": "def list_items(items, page=None, per_page=None):\\n    if page is None and per_page is None: return list(items)\\n    if page is None or per_page is None: raise ValueError(\\"page and per_page must be supplied together\\")\\n    if page < 1 or per_page < 1: raise ValueError(\\"page and per_page must be positive\\")\\n    start=(page-1)*per_page\\n    return list(items)[start:start+per_page]\\ndef summarize_page(items, page=None, per_page=None):\\n    selected=list_items(items, page=page, per_page=per_page)\\n    return {\\"count\\":len(selected),\\"ids\\":[item[\\"id\\"] for item in selected]}\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

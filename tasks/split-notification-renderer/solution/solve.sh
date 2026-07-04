#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"notifications/__init__.py": "from .html import render_html\\nfrom .text import render_text\\n__all__ = [\\"render_html\\", \\"render_text\\"]\\n", "notifications/html.py": "def render_html(n): return f\\"<article class=\'{n[\'severity\']}\'><h1>{n[\'title\']}</h1><p>{n[\'body\']}</p></article>\\"\\n", "notifications/renderer.py": "from .html import render_html\\nfrom .text import render_text\\n__all__ = [\\"render_html\\", \\"render_text\\"]\\n", "notifications/text.py": "def render_text(n): return f\\"[{n[\'severity\'].upper()}] {n[\'title\']}: {n[\'body\']}\\"\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

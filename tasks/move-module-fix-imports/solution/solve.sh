#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"app.py": "from text_tools.slug import slugify\\n\\ndef build_slug(title):\\n    return slugify(title)\\n", "text_tools/__init__.py": "from .slug import slugify\\n__all__ = [\\"slugify\\"]\\n", "text_tools/slug.py": "def slugify(value):\\n    return value.strip().lower().replace(\\" \\", \\"-\\")\\n", "tools/slugify.py": "from text_tools.slug import slugify\\n__all__ = [\\"slugify\\"]\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

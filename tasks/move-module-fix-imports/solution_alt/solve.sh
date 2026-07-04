#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

app = Path(os.environ.get("APP_DIR", "/app"))
old_module = app / "tools" / "slugify.py"
helper_source = old_module.read_text()

new_package = app / "text_tools"
new_package.mkdir(exist_ok=True)
(new_package / "slug.py").write_text(helper_source)
(new_package / "__init__.py").write_text("from .slug import slugify\n\n__all__ = [\"slugify\"]\n")

(app / "tools" / "slugify.py").write_text(
    "from text_tools.slug import slugify\n\n__all__ = [\"slugify\"]\n"
)

app_path = app / "app.py"
app_path.write_text(app_path.read_text().replace("from tools.slugify import", "from text_tools.slug import"))
PY

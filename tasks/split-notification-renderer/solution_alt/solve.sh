#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

app = Path(os.environ.get("APP_DIR", "/app"))
package = app / "notifications"
(package / "text.py").write_text(
    """def render_text(notification):
    severity = notification["severity"].upper()
    return f"[{severity}] {notification['title']}: {notification['body']}"
"""
)
(package / "html.py").write_text(
    """def render_html(notification):
    return (
        f"<article class='{notification['severity']}'>"
        f"<h1>{notification['title']}</h1>"
        f"<p>{notification['body']}</p>"
        "</article>"
    )
"""
)
(package / "renderer.py").write_text(
    "from .html import render_html\nfrom .text import render_text\n\n__all__ = [\"render_html\", \"render_text\"]\n"
)
(package / "__init__.py").write_text(
    "from .html import render_html\nfrom .text import render_text\n\n__all__ = [\"render_html\", \"render_text\"]\n"
)
PY

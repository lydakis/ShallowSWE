#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/catalog_api/items.py" <<'PY'
from __future__ import annotations


def _pagination_window(page: int | None, per_page: int | None) -> tuple[int, int] | None:
    if page is None and per_page is None:
        return None
    if page is None or per_page is None:
        raise ValueError("page and per_page must be supplied together")
    if page <= 0 or per_page <= 0:
        raise ValueError("page and per_page must be positive")
    start = (page - 1) * per_page
    return start, start + per_page


def list_items(items, page=None, per_page=None):
    values = list(items)
    window = _pagination_window(page, per_page)
    if window is None:
        return values
    start, end = window
    return values[start:end]


def summarize_page(items, page=None, per_page=None):
    selected = list_items(items, page=page, per_page=per_page)
    return {"count": len(selected), "ids": [item["id"] for item in selected]}
PY

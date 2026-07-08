#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "notifier" / "renderer.py"
path.write_text(
    '''from __future__ import annotations

from html import escape
import json
from pathlib import Path


CATALOG_DIR = Path(__file__).parent / "catalogs"


def _read_catalog(name: str) -> dict[str, str]:
    file_path = CATALOG_DIR / f"{name}.json"
    return json.loads(file_path.read_text()) if file_path.exists() else {}


def _locales(locale: str) -> list[str]:
    result = [locale]
    if "-" in locale:
        result.append(locale.split("-", 1)[0])
    result.append("default")
    return list(dict.fromkeys(result))


def _fill(template: str, variables: dict[str, object]) -> str:
    safe = {key: escape(str(value), quote=True) for key, value in variables.items()}
    class Missing(dict):
        def __missing__(self, key: str) -> str:
            return ""
    return template.format_map(Missing(safe))


def render_event(event: dict[str, object]) -> dict[str, str]:
    locale = str(event.get("locale") or "default")
    template_name = str(event["template"])
    template = None
    for candidate in _locales(locale):
        catalog = _read_catalog(candidate)
        if template_name in catalog:
            template = catalog[template_name]
            break
    if template is None:
        raise KeyError(template_name)
    return {
        "id": str(event["id"]),
        "locale": locale,
        "body": _fill(template, dict(event.get("vars") or {})),
    }
'''
)
PY

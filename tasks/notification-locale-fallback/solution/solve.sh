#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "notifier" / "renderer.py"
path.write_text(
    '''from __future__ import annotations

from collections import defaultdict
from html import escape
import json
from pathlib import Path


CATALOG_DIR = Path(__file__).parent / "catalogs"


class SafeVars(defaultdict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


def _load(locale: str) -> dict[str, str]:
    path = CATALOG_DIR / f"{locale}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _fallback_chain(locale: str) -> list[str]:
    chain = [locale]
    if "-" in locale:
        chain.append(locale.split("-", 1)[0])
    chain.append("default")
    seen: list[str] = []
    for item in chain:
        if item not in seen:
            seen.append(item)
    return seen


def _template(locale: str, key: str) -> str:
    for candidate in _fallback_chain(locale):
        catalog = _load(candidate)
        if key in catalog:
            return catalog[key]
    raise KeyError(key)


def render_event(event: dict[str, object]) -> dict[str, str]:
    locale = str(event.get("locale") or "default")
    variables = {key: escape(str(value), quote=True) for key, value in dict(event.get("vars") or {}).items()}
    body = _template(locale, str(event["template"])).format_map(SafeVars(str, variables))
    return {"id": str(event["id"]), "locale": locale, "body": body}
'''
)
PY

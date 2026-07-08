from __future__ import annotations

import json
from pathlib import Path


CATALOG_DIR = Path(__file__).parent / "catalogs"


def load_catalog(locale: str) -> dict[str, str]:
    path = CATALOG_DIR / f"{locale}.json"
    if not path.exists():
        path = CATALOG_DIR / "default.json"
    return json.loads(path.read_text())


def render_event(event: dict[str, object]) -> dict[str, str]:
    locale = str(event.get("locale") or "default")
    template = str(event["template"])
    variables = dict(event.get("vars") or {})
    catalog = load_catalog(locale)
    message = catalog[template].format(**variables)
    return {"id": str(event["id"]), "locale": locale, "body": message}

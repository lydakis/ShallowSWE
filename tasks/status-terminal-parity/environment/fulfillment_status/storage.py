from __future__ import annotations

from pathlib import Path
import json


def load_orders(path: str | Path) -> list[dict[str, str]]:
    return json.loads(Path(path).read_text())


def save_orders(path: str | Path, orders: list[dict[str, str]]) -> None:
    Path(path).write_text(json.dumps(orders, indent=2, sort_keys=True) + "\n")

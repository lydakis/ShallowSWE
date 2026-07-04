from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class Order:
    id: str
    region: str
    account: str
    state: str
    ready: bool


def load_orders(path: str | Path) -> list[Order]:
    rows = json.loads(Path(path).read_text())
    return [Order(**row) for row in rows]

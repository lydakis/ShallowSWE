from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class Order:
    id: str
    region: str
    status: str
    archived: bool


def load_orders(path: str | Path) -> list[Order]:
    raw_orders = json.loads(Path(path).read_text())
    return [
        Order(
            id=str(row["id"]),
            region=str(row["region"]),
            status=str(row["status"]),
            archived=bool(row["archived"]),
        )
        for row in raw_orders
    ]

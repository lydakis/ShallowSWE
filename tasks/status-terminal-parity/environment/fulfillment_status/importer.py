from __future__ import annotations

from pathlib import Path
import csv

from .statuses import normalize_status


def import_orders_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    orders: list[dict[str, str]] = []
    for row in rows:
        orders.append(
            {
                "order_id": row["order_id"],
                "status": normalize_status(row["status"]),
                "customer": row.get("customer", ""),
            }
        )
    return orders

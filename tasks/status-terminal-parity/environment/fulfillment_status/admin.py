from __future__ import annotations

from .statuses import StatusError, known_statuses


def repair_order_status(
    orders: list[dict[str, str]],
    order_id: str,
    raw_status: str,
) -> list[dict[str, str]]:
    status = raw_status.strip().lower()
    if status not in known_statuses():
        raise StatusError(f"unknown status: {raw_status}")

    found = False
    updated: list[dict[str, str]] = []
    for order in orders:
        next_order = dict(order)
        if next_order["order_id"] == order_id:
            next_order["status"] = status
            found = True
        updated.append(next_order)
    if not found:
        raise KeyError(f"unknown order: {order_id}")
    return updated

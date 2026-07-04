from __future__ import annotations

from .statuses import StatusError


CARRIER_STATUS_MAP = {
    "delivered": "delivered",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "lost": "lost",
    "lost_in_transit": "lost",
    "hold": "hold",
    "pending_review": "pending_review",
    "out_for_delivery": "out_for_delivery",
}


def apply_carrier_webhook(
    orders: list[dict[str, str]],
    event: dict[str, str],
) -> list[dict[str, str]]:
    order_id = event["order_id"]
    raw_status = event["carrier_status"].strip().lower()
    if raw_status not in CARRIER_STATUS_MAP:
        raise StatusError(f"unknown carrier status: {event['carrier_status']}")
    status = CARRIER_STATUS_MAP[raw_status]

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

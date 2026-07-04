from __future__ import annotations

from collections import Counter

from .statuses import is_successful_status


REPORT_TERMINAL_STATUSES = {"delivered", "cancelled", "lost"}


def build_report(orders: list[dict[str, str]]) -> dict[str, object]:
    by_status = Counter(order["status"] for order in orders)
    terminal_order_ids = [
        order["order_id"] for order in orders if order["status"] in REPORT_TERMINAL_STATUSES
    ]
    successful_order_ids = [
        order["order_id"] for order in orders if is_successful_status(order["status"])
    ]
    return {
        "total": len(orders),
        "terminal": len(terminal_order_ids),
        "successful": len(successful_order_ids),
        "open": len(orders) - len(terminal_order_ids),
        "terminal_order_ids": terminal_order_ids,
        "successful_order_ids": successful_order_ids,
        "by_status": dict(sorted(by_status.items())),
    }

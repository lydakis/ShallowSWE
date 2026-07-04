#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/fulfillment_status/statuses.py" <<'PY'
from __future__ import annotations


class StatusError(ValueError):
    pass


OPEN_STATUSES = {
    "new",
    "packed",
    "shipped",
    "out_for_delivery",
    "hold",
    "pending_review",
}
TERMINAL_STATUSES = {"delivered", "cancelled", "lost", "return_to_sender"}
SUCCESSFUL_STATUSES = {"delivered"}
STATUS_ALIASES = {
    "canceled": "cancelled",
    "lost_in_transit": "lost",
    "rts": "return_to_sender",
}


def known_statuses() -> set[str]:
    return set(OPEN_STATUSES | TERMINAL_STATUSES)


def normalize_status(raw_status: str) -> str:
    status = STATUS_ALIASES.get(raw_status.strip().lower(), raw_status.strip().lower())
    if status not in known_statuses():
        raise StatusError(f"unknown status: {raw_status}")
    return status


def is_terminal_status(raw_status: str) -> bool:
    return normalize_status(raw_status) in TERMINAL_STATUSES


def is_successful_status(raw_status: str) -> bool:
    return normalize_status(raw_status) in SUCCESSFUL_STATUSES


def status_help() -> str:
    return "known statuses: " + ", ".join(sorted(known_statuses() | set(STATUS_ALIASES)))
PY

cat > "$APP_DIR/fulfillment_status/admin.py" <<'PY'
from __future__ import annotations

from .statuses import normalize_status


def repair_order_status(
    orders: list[dict[str, str]],
    order_id: str,
    raw_status: str,
) -> list[dict[str, str]]:
    canonical = normalize_status(raw_status)
    found = False
    updated: list[dict[str, str]] = []
    for order in orders:
        next_order = dict(order)
        if next_order["order_id"] == order_id:
            next_order["status"] = canonical
            found = True
        updated.append(next_order)
    if not found:
        raise KeyError(f"unknown order: {order_id}")
    return updated
PY

cat > "$APP_DIR/fulfillment_status/webhook.py" <<'PY'
from __future__ import annotations

from .statuses import normalize_status


def apply_carrier_webhook(
    orders: list[dict[str, str]],
    event: dict[str, str],
) -> list[dict[str, str]]:
    order_id = event["order_id"]
    canonical = normalize_status(event["carrier_status"])
    found = False
    updated: list[dict[str, str]] = []
    for order in orders:
        next_order = dict(order)
        if next_order["order_id"] == order_id:
            next_order["status"] = canonical
            found = True
        updated.append(next_order)
    if not found:
        raise KeyError(f"unknown order: {order_id}")
    return updated
PY

cat > "$APP_DIR/fulfillment_status/report.py" <<'PY'
from __future__ import annotations

from collections import Counter

from .statuses import is_successful_status, is_terminal_status


def build_report(orders: list[dict[str, str]]) -> dict[str, object]:
    by_status = Counter(order["status"] for order in orders)
    terminal_order_ids = [order["order_id"] for order in orders if is_terminal_status(order["status"])]
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
PY

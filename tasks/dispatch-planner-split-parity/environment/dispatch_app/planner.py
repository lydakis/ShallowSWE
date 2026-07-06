from __future__ import annotations

from datetime import datetime

from .config import DispatchConfig
from .orders import Order


def _parse_promised_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def plan_dispatch(orders: list[Order], config: DispatchConfig) -> list[str]:
    selected: list[Order] = []
    for order in orders:
        if config.region and order.region != config.region:
            continue
        if config.account and order.account != config.account:
            continue
        if not order.ready:
            continue
        if order.state == "archived" and not config.include_archived:
            continue
        if order.state not in {"active", "archived"}:
            continue
        selected.append(order)

    # Known bug: ties on promised_at sort by id before priority.
    selected.sort(key=lambda order: (_parse_promised_at(order.promised_at), order.id, -order.priority))
    return [order.id for order in selected]

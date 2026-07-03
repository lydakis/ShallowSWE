from __future__ import annotations

from .config import DispatchConfig
from .orders import Order


def plan_dispatch(orders: list[Order], config: DispatchConfig) -> list[str]:
    selected: list[str] = []
    for order in orders:
        if config.region and order.region != config.region:
            continue
        if order.status != "ready":
            continue
        if order.archived and not config.include_archived:
            continue
        selected.append(order.id)
    return selected

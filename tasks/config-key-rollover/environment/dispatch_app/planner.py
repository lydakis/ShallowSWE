from __future__ import annotations

from .config import DispatchConfig
from .orders import Order


def plan_dispatch(orders: list[Order], config: DispatchConfig) -> list[str]:
    selected: list[str] = []
    for order in orders:
        if config.region and order.region != config.region:
            continue
        if config.account and order.account != config.account:
            continue
        if not order.ready:
            continue
        if order.state == "archived" and not config.include_closed:
            continue
        if order.state not in {"active", "archived"}:
            continue
        selected.append(order.id)
    return selected

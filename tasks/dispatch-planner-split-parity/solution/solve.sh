#!/usr/bin/env bash
set -euo pipefail

cd /app

mkdir -p dispatch_app/pipeline

cat > dispatch_app/pipeline/__init__.py <<'PY'
"""Filter and ordering pipeline for dispatch planning."""

from .planner import plan_dispatch

__all__ = ["plan_dispatch"]
PY

cat > dispatch_app/pipeline/filters.py <<'PY'
from __future__ import annotations

from dispatch_app.config import DispatchConfig
from dispatch_app.orders import Order


def is_dispatchable(order: Order, config: DispatchConfig) -> bool:
    if config.region and order.region != config.region:
        return False
    if config.account and order.account != config.account:
        return False
    if not order.ready:
        return False
    if order.state == "archived" and not config.include_archived:
        return False
    return order.state in {"active", "archived"}
PY

cat > dispatch_app/pipeline/ordering.py <<'PY'
from __future__ import annotations

from datetime import datetime

from dispatch_app.orders import Order


def parse_promised_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def dispatch_sort_key(order: Order) -> tuple[datetime, int, str]:
    return (parse_promised_at(order.promised_at), -order.priority, order.id)
PY

cat > dispatch_app/pipeline/planner.py <<'PY'
from __future__ import annotations

from dispatch_app.config import DispatchConfig
from dispatch_app.orders import Order

from .filters import is_dispatchable
from .ordering import dispatch_sort_key


def plan_dispatch(orders: list[Order], config: DispatchConfig) -> list[str]:
    selected = [order for order in orders if is_dispatchable(order, config)]
    selected.sort(key=dispatch_sort_key)
    return [order.id for order in selected]
PY

cat > dispatch_app/planner.py <<'PY'
from __future__ import annotations

from .pipeline.planner import plan_dispatch

__all__ = ["plan_dispatch"]
PY

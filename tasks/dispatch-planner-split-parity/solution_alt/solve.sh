#!/usr/bin/env bash
set -euo pipefail

cd /app

mkdir -p dispatch_app/pipeline

cat > dispatch_app/pipeline/__init__.py <<'PY'
"""Dispatch planning pipeline."""
PY

cat > dispatch_app/pipeline/filters.py <<'PY'
from __future__ import annotations

from dispatch_app.config import DispatchConfig
from dispatch_app.orders import Order


def region_matches(order: Order, config: DispatchConfig) -> bool:
    return config.region is None or order.region == config.region


def account_matches(order: Order, config: DispatchConfig) -> bool:
    return config.account is None or order.account == config.account


def state_allowed(order: Order, config: DispatchConfig) -> bool:
    return order.state == "active" or (order.state == "archived" and config.include_archived)


def is_dispatchable(order: Order, config: DispatchConfig) -> bool:
    return (
        region_matches(order, config)
        and account_matches(order, config)
        and order.ready
        and state_allowed(order, config)
    )
PY

cat > dispatch_app/pipeline/ordering.py <<'PY'
from __future__ import annotations

from datetime import datetime, timezone

from dispatch_app.orders import Order


def _timestamp(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).timestamp()


def dispatch_sort_key(order: Order) -> tuple[float, int, str]:
    return (_timestamp(order.promised_at), -int(order.priority), order.id)
PY

cat > dispatch_app/pipeline/planner.py <<'PY'
from __future__ import annotations

from dispatch_app.config import DispatchConfig
from dispatch_app.orders import Order

from .filters import is_dispatchable
from .ordering import dispatch_sort_key


def plan_dispatch(orders: list[Order], config: DispatchConfig) -> list[str]:
    return [
        order.id
        for order in sorted(
            (order for order in orders if is_dispatchable(order, config)),
            key=dispatch_sort_key,
        )
    ]
PY

cat > dispatch_app/planner.py <<'PY'
from __future__ import annotations

from .pipeline.planner import plan_dispatch

__all__ = ["plan_dispatch"]
PY

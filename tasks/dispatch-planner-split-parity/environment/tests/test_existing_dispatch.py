from __future__ import annotations

from dispatch_app.config import DispatchConfig
from dispatch_app.orders import load_orders
from dispatch_app.planner import plan_dispatch


def test_existing_filters_still_select_ready_active_orders() -> None:
    orders = load_orders("/app/orders.json")

    assert plan_dispatch(
        orders,
        DispatchConfig(region="west", account="acme", include_archived=False),
    ) == ["DSP-100", "DSP-101", "DSP-110", "DSP-120"]


def test_existing_archived_flag_includes_archived_orders() -> None:
    orders = load_orders("/app/orders.json")

    assert plan_dispatch(
        orders,
        DispatchConfig(region="west", account="acme", include_archived=True),
    ) == ["DSP-100", "DSP-102", "DSP-101", "DSP-110", "DSP-120"]

from __future__ import annotations

import argparse

from .config import load_config
from .orders import load_orders
from .planner import plan_dispatch


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dispatch-plan",
        epilog="Environment: DISPATCH_REGION, DISPATCH_ACCOUNT, DISPATCH_INCLUDE_CLOSED=1",
    )
    parser.add_argument("--orders", default="/app/orders.json")
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()

    config = load_config(args.env_file)
    for order_id in plan_dispatch(load_orders(args.orders), config):
        print(order_id)


if __name__ == "__main__":
    main()

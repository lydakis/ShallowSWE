#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

config = Path("/app/dispatch_app/config.py")
config.write_text(
    '''from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class DispatchConfig:
    region: str | None
    account: str | None
    include_closed: bool
    visibility: str


def load_env_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _truthy(value: str | None) -> bool:
    return value in {"1", "true", "yes", "on"}


def _load_visibility(values: dict[str, str]) -> str:
    if values.get("DISPATCH_VISIBILITY"):
        visibility = values["DISPATCH_VISIBILITY"].strip().lower()
        if visibility not in {"active", "archived", "all"}:
            raise ValueError("unsupported DISPATCH_VISIBILITY")
        return visibility
    if _truthy(values.get("DISPATCH_INCLUDE_CLOSED")):
        return "all"
    return "active"


def load_config(env_file: str | Path | None = None) -> DispatchConfig:
    values = dict(os.environ)
    if env_file is not None:
        values.update(load_env_file(env_file))
    visibility = _load_visibility(values)
    return DispatchConfig(
        region=values.get("DISPATCH_REGION") or None,
        account=values.get("DISPATCH_ACCOUNT") or None,
        include_closed=visibility == "all",
        visibility=visibility,
    )
'''
)

Path("/app/dispatch_app/planner.py").write_text(
    '''from __future__ import annotations

from .config import DispatchConfig
from .orders import Order


def _visible(state: str, visibility: str) -> bool:
    if visibility == "all":
        return state in {"active", "archived"}
    return state == visibility


def plan_dispatch(orders: list[Order], config: DispatchConfig) -> list[str]:
    selected: list[str] = []
    for order in orders:
        if config.region and order.region != config.region:
            continue
        if config.account and order.account != config.account:
            continue
        if order.ready and _visible(order.state, config.visibility):
            selected.append(order.id)
    return selected
'''
)

Path("/app/dispatch_app/cli.py").write_text(
    '''from __future__ import annotations

import argparse

from .config import load_config
from .orders import load_orders
from .planner import plan_dispatch


HELP = "Environment: DISPATCH_VISIBILITY=active|archived|all; old DISPATCH_INCLUDE_CLOSED=1 still works"


def main() -> None:
    parser = argparse.ArgumentParser(prog="dispatch-plan", epilog=HELP)
    parser.add_argument("--orders", default="/app/orders.json")
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()

    config = load_config(args.env_file)
    for order_id in plan_dispatch(load_orders(args.orders), config):
        print(order_id)


if __name__ == "__main__":
    main()
'''
)

Path("/app/README.md").write_text(
    '''# Dispatch Planner

Use `DISPATCH_VISIBILITY=active|archived|all` with optional `DISPATCH_REGION` and
`DISPATCH_ACCOUNT` filters. `active` is the default, `archived` shows archived dispatchable
orders only, and `all` shows both active and archived dispatchable orders.

`DISPATCH_INCLUDE_CLOSED=1` remains a compatibility alias for `all` when
`DISPATCH_VISIBILITY` is absent.

Run `python -m dispatch_app.cli --orders /app/orders.json --env-file /app/.env.nightly`.
The command prints one order id per line.
'''
)

Path("/app/.env.nightly").write_text(
    "DISPATCH_REGION=west\nDISPATCH_ACCOUNT=acme\nDISPATCH_VISIBILITY=all\n"
)
PY

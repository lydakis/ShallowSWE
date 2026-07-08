#!/usr/bin/env bash
set -euo pipefail

cat > /app/dispatch_app/config.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


VALID_VISIBILITY = {"active", "archived", "all"}


@dataclass(frozen=True)
class DispatchConfig:
    region: str | None
    account: str | None
    visibility: str

    @property
    def include_closed(self) -> bool:
        return self.visibility == "all"


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


def _visibility_from(values: dict[str, str]) -> str:
    raw_visibility = values.get("DISPATCH_VISIBILITY")
    if raw_visibility:
        visibility = raw_visibility.strip().lower()
        if visibility not in VALID_VISIBILITY:
            raise ValueError("DISPATCH_VISIBILITY must be active, archived, or all")
        return visibility
    if _truthy(values.get("DISPATCH_INCLUDE_CLOSED")):
        return "all"
    return "active"


def load_config(env_file: str | Path | None = None) -> DispatchConfig:
    values = dict(os.environ)
    if env_file is not None:
        values.update(load_env_file(env_file))

    return DispatchConfig(
        region=values.get("DISPATCH_REGION") or None,
        account=values.get("DISPATCH_ACCOUNT") or None,
        visibility=_visibility_from(values),
    )
PY

cat > /app/dispatch_app/planner.py <<'PY'
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
        if order.state not in {"active", "archived"}:
            continue
        if config.visibility != "all" and order.state != config.visibility:
            continue
        selected.append(order.id)
    return selected
PY

cat > /app/dispatch_app/cli.py <<'PY'
from __future__ import annotations

import argparse

from .config import load_config
from .orders import load_orders
from .planner import plan_dispatch


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dispatch-plan",
        epilog=(
            "Environment: DISPATCH_REGION, DISPATCH_ACCOUNT, "
            "DISPATCH_VISIBILITY=active|archived|all"
        ),
    )
    parser.add_argument("--orders", default="/app/orders.json")
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()

    config = load_config(args.env_file)
    for order_id in plan_dispatch(load_orders(args.orders), config):
        print(order_id)


if __name__ == "__main__":
    main()
PY

cat > /app/README.md <<'MD'
# Dispatch Planner

Run a dispatch plan with:

```sh
python -m dispatch_app.cli --orders /app/orders.json --env-file /app/.env.nightly
```

Environment keys:

- `DISPATCH_REGION`: optional region filter.
- `DISPATCH_ACCOUNT`: optional account filter.
- `DISPATCH_VISIBILITY=active|archived|all`: controls which dispatchable orders are shown.

Visibility values:

- `active`: active dispatchable orders only.
- `archived`: archived dispatchable orders only.
- `all`: active and archived dispatchable orders.

The legacy `DISPATCH_INCLUDE_CLOSED=1` key remains an alias for `all` when
`DISPATCH_VISIBILITY` is absent.

The command prints one order id per line.
MD

cat > /app/.env.nightly <<'EOF'
DISPATCH_REGION=west
DISPATCH_ACCOUNT=acme
DISPATCH_VISIBILITY=all
EOF

cat > /app/.env.legacy <<'EOF'
DISPATCH_REGION=west
DISPATCH_ACCOUNT=acme
DISPATCH_VISIBILITY=all
EOF

cat > /app/.env.preview <<'EOF'
DISPATCH_REGION=east
DISPATCH_ACCOUNT=acme
DISPATCH_VISIBILITY=all
EOF

cat > /app/.env.backfill <<'EOF'
DISPATCH_REGION=west
DISPATCH_ACCOUNT=globex
DISPATCH_VISIBILITY=all
EOF

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

python3 - <<'PY'
from pathlib import Path
import os

script = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "build_schedule.py"
script.write_text(
    '''from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import json


FIELDS = [
    "account_id",
    "event_id",
    "action",
    "effective_start",
    "effective_end",
    "period_days",
    "remaining_days",
    "amount_usd_cents",
]


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def action_for(row: dict[str, str], old_price: int, new_price: int) -> str:
    if row["new_plan"] == "cancelled":
        return "cancel"
    if new_price > old_price:
        return "upgrade"
    if new_price < old_price:
        return "downgrade"
    return "noop"


def main() -> None:
    root = Path.cwd()
    schedule: list[dict[str, str]] = []
    event_count = 0
    with (root / "input" / "subscription_events.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            event_count += 1
            start = parse_date(row["period_start"])
            end = parse_date(row["period_end"])
            event = parse_date(row["event_date"])
            old_price = int(row["old_monthly_cents"])
            new_price = 0 if row["new_plan"] == "cancelled" else int(row["new_monthly_cents"])
            action = action_for(row, old_price, new_price)
            if action == "noop":
                continue
            period_days = (end - start).days
            remaining_days = (end - event).days
            amount = round_half_up(
                Decimal(new_price - old_price) * Decimal(remaining_days) / Decimal(period_days)
            )
            schedule.append(
                {
                    "account_id": row["account_id"],
                    "event_id": row["event_id"],
                    "action": action,
                    "effective_start": row["event_date"],
                    "effective_end": row["period_end"],
                    "period_days": str(period_days),
                    "remaining_days": str(remaining_days),
                    "amount_usd_cents": str(amount),
                }
            )

    schedule.sort(key=lambda row: (row["account_id"], row["event_id"]))
    output = root / "output"
    output.mkdir(exist_ok=True)
    with (output / "schedule.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\\n")
        writer.writeheader()
        writer.writerows(schedule)
    amounts = [int(row["amount_usd_cents"]) for row in schedule]
    summary = {
        "event_count": event_count,
        "line_item_count": len(schedule),
        "total_charge_cents": sum(amount for amount in amounts if amount > 0),
        "total_credit_cents": -sum(amount for amount in amounts if amount < 0),
        "net_total_cents": sum(amounts),
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\\n")


if __name__ == "__main__":
    main()
'''
)
PY

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


def d(value: str) -> date:
    return date.fromisoformat(value)


def cents(delta: int, remaining: int, days: int) -> int:
    return int((Decimal(delta) * Decimal(remaining) / Decimal(days)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def main() -> None:
    root = Path.cwd()
    output_rows = []
    total_events = 0
    with (root / "input" / "subscription_events.csv").open(newline="") as source:
        for row in csv.DictReader(source):
            total_events += 1
            old_price = int(row["old_monthly_cents"])
            new_price = 0 if row["new_plan"] == "cancelled" else int(row["new_monthly_cents"])
            if row["new_plan"] == "cancelled":
                action = "cancel"
            elif new_price > old_price:
                action = "upgrade"
            elif new_price < old_price:
                action = "downgrade"
            else:
                continue
            start = d(row["period_start"])
            end = d(row["period_end"])
            event = d(row["event_date"])
            period = (end - start).days
            remaining = (end - event).days
            output_rows.append(
                {
                    "account_id": row["account_id"],
                    "event_id": row["event_id"],
                    "action": action,
                    "effective_start": row["event_date"],
                    "effective_end": row["period_end"],
                    "period_days": str(period),
                    "remaining_days": str(remaining),
                    "amount_usd_cents": str(cents(new_price - old_price, remaining, period)),
                }
            )

    output_rows.sort(key=lambda item: (item["account_id"], item["event_id"]))
    out = root / "output"
    out.mkdir(exist_ok=True)
    fields = ["account_id", "event_id", "action", "effective_start", "effective_end", "period_days", "remaining_days", "amount_usd_cents"]
    with (out / "schedule.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\\n")
        writer.writeheader()
        writer.writerows(output_rows)
    values = [int(row["amount_usd_cents"]) for row in output_rows]
    charge = sum(value for value in values if value > 0)
    credit = sum(-value for value in values if value < 0)
    (out / "summary.json").write_text(json.dumps({"event_count": total_events, "line_item_count": len(output_rows), "net_total_cents": sum(values), "total_charge_cents": charge, "total_credit_cents": credit}, sort_keys=True) + "\\n")


if __name__ == "__main__":
    main()
'''
)
PY

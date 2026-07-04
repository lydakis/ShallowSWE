#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv
import json


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def money(value: float) -> str:
    return f"{value:.2f}"


def main() -> None:
    root = Path.cwd()
    invoices = [row for row in read_csv(root / "input" / "invoices.csv") if row["status"] == "paid"]
    credits_by_invoice: dict[str, float] = defaultdict(float)
    for credit in read_csv(root / "input" / "credits.csv"):
        credits_by_invoice[credit["invoice_id"]] += float(credit["amount"])

    plans: dict[str, dict[str, float]] = defaultdict(lambda: {"gross": 0.0, "credits": 0.0})
    for invoice in invoices:
        plan = invoice["plan"]
        plans[plan]["gross"] += float(invoice["amount"])
        plans[plan]["credits"] += credits_by_invoice[invoice["invoice_id"]]

    output = root / "output"
    output.mkdir(exist_ok=True)
    with (output / "revenue_rollup.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["plan", "gross", "credits", "net"],
            lineterminator="\n",
        )
        writer.writeheader()
        for plan in sorted(plans):
            gross = plans[plan]["gross"]
            credits = plans[plan]["credits"]
            writer.writerow(
                {
                    "plan": plan,
                    "gross": money(gross),
                    "credits": money(credits),
                    "net": money(gross - credits),
                }
            )

    open_disputes = [row for row in read_csv(root / "input" / "disputes.csv") if row["status"] == "open"]
    open_disputes.sort(key=lambda row: row["dispute_id"])
    with (output / "adjustments.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["dispute_id", "invoice_id", "amount", "status"],
            lineterminator="\n",
        )
        writer.writeheader()
        for dispute in open_disputes:
            writer.writerow(
                {
                    "dispute_id": dispute["dispute_id"],
                    "invoice_id": dispute["invoice_id"],
                    "amount": money(float(dispute["amount"])),
                    "status": dispute["status"],
                }
            )

    recognized = sum(data["gross"] - data["credits"] for data in plans.values())
    summary = {"open_disputes": len(open_disputes), "recognized_revenue": recognized}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

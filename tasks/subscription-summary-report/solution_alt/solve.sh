#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import json


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    root = Path.cwd()
    rows = read_rows(root / "input" / "subscriptions.csv")
    billable = [row for row in rows if row["status"] != "trialing"]
    active = [row for row in rows if row["status"] == "active"]
    cancelled = [row for row in rows if row["status"] == "cancelled"]

    output = root / "output"
    output.mkdir(exist_ok=True)
    summary = {
        "active_accounts": len(active),
        "churned_accounts": len(cancelled),
        "mrr": sum(int(row["mrr"]) for row in active),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    plan_counts = Counter(row["plan"] for row in billable)
    with (output / "plan_counts.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["plan", "count"], lineterminator="\n")
        writer.writeheader()
        for plan, count in sorted(plan_counts.items()):
            writer.writerow({"plan": plan, "count": count})


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

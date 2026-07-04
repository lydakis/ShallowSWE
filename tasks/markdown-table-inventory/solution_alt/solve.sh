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


FIELDS = ["team", "service", "owner", "status"]


def parse_markdown_table(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(set(cell) <= {"-", " "} for cell in cells):
            continue
        if headers is None:
            headers = [cell.lower() for cell in cells]
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def main() -> None:
    root = Path.cwd()
    active = [
        {field: row[field] for field in FIELDS}
        for row in parse_markdown_table((root / "input" / "inventory.md").read_text())
        if row.get("status") != "retired"
    ]
    active.sort(key=lambda row: (row["team"], row["service"]))

    output = root / "output"
    output.mkdir(exist_ok=True)
    with (output / "inventory.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(active)

    counts = Counter(row["team"] for row in active)
    summary = {"active_services": len(active), "teams": dict(sorted(counts.items()))}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

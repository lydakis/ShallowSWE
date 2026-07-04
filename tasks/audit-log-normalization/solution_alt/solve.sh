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
import re


def normalize_action(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def main() -> None:
    root = Path.cwd()
    normalized: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []
    for line in (root / "input" / "audit.log").read_text().splitlines():
        parts = line.split("|")
        if len(parts) != 4:
            rejects.append({"line": line, "reason": "malformed_line"})
            continue
        timestamp, actor, action, result = [part.strip() for part in parts]
        normalized.append(
            {
                "timestamp": timestamp,
                "actor": actor,
                "action": normalize_action(action),
                "result": result,
            }
        )

    normalized.sort(key=lambda row: (row["timestamp"], row["actor"]))
    output = root / "output"
    output.mkdir(exist_ok=True)
    with (output / "normalized.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "actor", "action", "result"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(normalized)

    with (output / "rejects.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["line", "reason"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rejects)

    actions = Counter(row["action"] for row in normalized)
    summary = {"actions": dict(sorted(actions.items())), "rejected": len(rejects), "rows": len(normalized)}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

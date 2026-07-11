#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import json


FIELDS = ["timestamp", "service", "method", "path", "status", "severity", "request_id"]


def classify(status_text: str) -> str | None:
    try:
        status = int(status_text)
    except ValueError:
        return None
    if not 100 <= status <= 599:
        return None
    if status >= 500:
        return "high"
    if status == 429:
        return "medium"
    return None


def main() -> None:
    root = Path.cwd()
    incidents: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []

    for line in (root / "input" / "access.log").read_text().splitlines():
        pieces = line.split()
        if len(pieces) != 6:
            rejects.append({"line": line, "reason": "malformed_line"})
            continue
        try:
            status = int(pieces[4])
        except ValueError:
            rejects.append({"line": line, "reason": "malformed_line"})
            continue
        if not 100 <= status <= 599:
            rejects.append({"line": line, "reason": "malformed_line"})
            continue
        severity = classify(pieces[4])
        if severity is None:
            continue
        incidents.append(dict(zip(FIELDS, [*pieces[:5], severity, pieces[5]], strict=True)))

    incidents.sort(key=lambda row: row["timestamp"])
    output = root / "output"
    output.mkdir(exist_ok=True)

    with (output / "incidents.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(incidents)

    with (output / "rejects.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["line", "reason"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rejects)

    summary = {
        "high": sum(row["severity"] == "high" for row in incidents),
        "medium": sum(row["severity"] == "medium" for row in incidents),
        "total_incidents": len(incidents),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

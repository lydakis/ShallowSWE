#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import json


INCIDENT_FIELDS = ["timestamp", "service", "method", "path", "status", "severity", "request_id"]


def main() -> None:
    root = Path.cwd()
    incidents: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []
    for raw_line in (root / "input" / "access.log").read_text().splitlines():
        parts = raw_line.split()
        if len(parts) != 6:
            rejects.append({"line": raw_line, "reason": "malformed_line"})
            continue
        timestamp, service, method, path, status, request_id = parts
        try:
            status_int = int(status)
        except ValueError:
            rejects.append({"line": raw_line, "reason": "malformed_line"})
            continue
        if not 100 <= status_int <= 599:
            rejects.append({"line": raw_line, "reason": "malformed_line"})
            continue
        severity = "high" if status_int >= 500 else "medium" if status_int == 429 else ""
        if severity:
            incidents.append(
                {
                    "timestamp": timestamp,
                    "service": service,
                    "method": method,
                    "path": path,
                    "status": status,
                    "severity": severity,
                    "request_id": request_id,
                }
            )
    incidents.sort(key=lambda row: row["timestamp"])
    output = root / "output"
    output.mkdir(parents=True, exist_ok=True)
    with (output / "incidents.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INCIDENT_FIELDS)
        writer.writeheader()
        writer.writerows(incidents)
    with (output / "rejects.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["line", "reason"])
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

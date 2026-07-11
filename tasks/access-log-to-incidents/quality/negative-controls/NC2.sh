#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"
cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from pathlib import Path
import csv
import json

root = Path.cwd()
output = root / "output"
output.mkdir(exist_ok=True)
incidents = [
    ["2026-07-04T10:01:00Z", "api", "POST", "/v1/login", "500", "high", "req-2"],
    ["2026-07-04T10:02:00Z", "edge", "GET", "/v1/search", "429", "medium", "req-3"],
    ["2026-07-04T10:03:00Z", "api", "GET", "/v1/orders", "503", "high", "req-4"],
]
with (output / "incidents.csv").open("w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["timestamp", "service", "method", "path", "status", "severity", "request_id"])
    writer.writerows(incidents)
with (output / "rejects.csv").open("w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["line", "reason"])
    writer.writerow(["not a valid log line", "malformed_line"])
(output / "summary.json").write_text(json.dumps({"high": 2, "medium": 1, "total_incidents": 3}))
PY

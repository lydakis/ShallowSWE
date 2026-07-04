#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
script = app / "scripts" / "build_outputs.py"
script.parent.mkdir(parents=True, exist_ok=True)
script.write_text(
    """from __future__ import annotations

from pathlib import Path
import csv
import json


FIELDS = ("timestamp", "service", "code", "message", "request_id")


def flatten(entry: dict[str, object]) -> dict[str, str]:
    error = entry.get("error") or {}
    context = entry.get("context") or {}
    return {
        "timestamp": str(entry["timestamp"]),
        "service": str(entry["service"]),
        "code": str(error["code"]),
        "message": str(error["message"]),
        "request_id": str(context.get("request_id", "")),
    }


def main() -> None:
    root = Path.cwd()
    entries = json.loads((root / "input" / "errors.json").read_text())
    output = root / "output" / "errors.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(flatten(entry) for entry in entries)


if __name__ == "__main__":
    main()
"""
)
subprocess.run(["python3", "scripts/build_outputs.py"], cwd=app, check=True)
PY

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
import json


def coerce(value: str) -> object:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    for parser in (int, float):
        try:
            return parser(value)
        except ValueError:
            pass
    return value


def parse_line(raw_line: str) -> tuple[str, object] | None:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, raw_value = (part.strip() for part in stripped.split("=", 1))
    if not key or not raw_value:
        return None
    return key, coerce(raw_value)


def main() -> None:
    root = Path.cwd()
    parsed = dict(
        item
        for line in (root / "input" / "flags.env").read_text().splitlines()
        if (item := parse_line(line)) is not None
    )
    output = root / "output" / "flags.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(parsed, indent=2, sort_keys=True) + "\\n")


if __name__ == "__main__":
    main()
"""
)
subprocess.run(["python3", "scripts/build_outputs.py"], cwd=app, check=True)
PY

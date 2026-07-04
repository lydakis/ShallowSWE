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


def normalize(raw_line: str) -> str | None:
    value = raw_line.partition("#")[0].strip().lower()
    return value or None


def main() -> None:
    root = Path.cwd()
    source = root / "input" / "allowlist.txt"
    domains = {
        domain
        for line in source.read_text().splitlines()
        if (domain := normalize(line)) is not None
    }
    output = root / "output" / "allowlist.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\\n".join(sorted(domains)) + ("\\n" if domains else ""))


if __name__ == "__main__":
    main()
"""
)
subprocess.run(["python3", "scripts/build_outputs.py"], cwd=app, check=True)
PY

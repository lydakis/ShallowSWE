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


def parse_bullet(line: str, index: int) -> dict[str, object] | None:
    if not line.startswith("- ["):
        return None
    marker, rest = line[3:].split("]", 1)
    owner, title = rest.strip().lstrip("[").split("]", 1)
    return {
        "id": f"rel-{index}",
        "owner": owner,
        "required": marker == "required",
        "title": title.strip(),
    }


def main() -> None:
    root = Path.cwd()
    items: list[dict[str, object]] = []
    for line in (root / "input" / "release-spec.md").read_text().splitlines():
        parsed = parse_bullet(line.strip(), len(items) + 1)
        if parsed is not None:
            items.append(parsed)
    output = root / "output" / "checklist.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(items, indent=2, sort_keys=True) + "\\n")


if __name__ == "__main__":
    main()
"""
)
subprocess.run(["python3", "scripts/build_outputs.py"], cwd=app, check=True)
PY

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
script = app / "scripts" / "apply_task.py"
script.parent.mkdir(parents=True, exist_ok=True)
script.write_text(
    """from __future__ import annotations

from pathlib import Path
import json


def apply_patch(root: Path, patch: dict[str, str]) -> None:
    target = root / "repo" / patch["file"]
    original = target.read_text() if target.exists() else ""
    addition = patch["append"]
    if addition not in original:
        target.write_text(original + addition)


def main() -> None:
    root = Path.cwd()
    applied: list[str] = []
    for path in sorted((root / "patches").glob("*.json")):
        patch = json.loads(path.read_text())
        if patch["id"].endswith("release-note"):
            apply_patch(root, patch)
            applied.append(patch["id"])
    (root / "applied_commits.txt").write_text("".join(f"{item}\\n" for item in applied))


if __name__ == "__main__":
    main()
"""
)
subprocess.run(["python3", "scripts/apply_task.py"], cwd=app, check=True)
PY

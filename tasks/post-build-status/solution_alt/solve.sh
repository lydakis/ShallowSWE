#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
script = app / "scripts" / "apply_task.py"
script.parent.mkdir(parents=True, exist_ok=True)
script.write_text(
    """from __future__ import annotations

from pathlib import Path
import json


def build_status(result: dict[str, object]) -> dict[str, str]:
    failed = list(result.get("failed") or [])
    state = "failure" if failed else "success"
    project = str(result["project"])
    suite = str(result["suite"])
    commit = str(result["commit"])
    if failed:
        body = f"{project} {suite} failed on {commit}: {', '.join(failed)}"
    else:
        body = f"{project} {suite} passed on {commit}: {result['passed']} tests"
    return {
        "body": body,
        "commit": commit,
        "context": f"ci/{suite}",
        "state": state,
    }


def main() -> None:
    root = Path.cwd()
    status = build_status(json.loads((root / "build_result.json").read_text()))
    api_state = root / "api_state"
    api_state.mkdir(parents=True, exist_ok=True)
    (api_state / "statuses.json").write_text(json.dumps([status], indent=2, sort_keys=True) + "\\n")
    (api_state / "calls.log").write_text(
        f"post_status {status['commit']} {status['context']} {status['state']}\\n"
    )


if __name__ == "__main__":
    main()
"""
)
subprocess.run(["python3", "scripts/apply_task.py"], cwd=app, check=True)
PY

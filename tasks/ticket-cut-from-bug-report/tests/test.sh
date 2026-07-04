#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import csv
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

app = Path(os.environ.get("APP_DIR", "/app"))

def run_script(script_name: str, root: Path) -> None:
    subprocess.run([sys.executable, str(root / "scripts" / script_name)], cwd=root, check=True)

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))

def assert_json(path: Path, expected: object) -> None:
    assert path.exists(), f"missing {path}"
    assert json.loads(path.read_text()) == expected

def assert_text(path: Path, expected: str) -> None:
    assert path.exists(), f"missing {path}"
    assert path.read_text() == expected

def copy_script_to_hidden(script_name: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name) / "app"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(app / "scripts" / script_name, root / "scripts" / script_name)
    return tmp, root
script = app / "scripts" / "apply_task.py"
assert script.exists(), "missing scripts/apply_task.py"
run_script("apply_task.py", app)
assert_json(app / 'api_state/tickets.json', [{'component': 'checkout', 'id': 'T-100', 'labels': ['bug', 'checkout'], 'priority': 'P1', 'status': 'open', 'title': 'Checkout 500 with saved card after coupon'}])
assert_text(app / 'api_state/calls.log', 'create_ticket T-100\n')
tmp, hidden = copy_script_to_hidden("apply_task.py")
with tmp:
    path = hidden / 'bug_report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# Bug report\n\nBilling payout retries return 503 in production.\n')
    path = hidden / 'api_state/tickets.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[]\n')
    path = hidden / 'api_state/calls.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('')
    run_script("apply_task.py", hidden)
    assert_json(hidden / 'api_state/tickets.json', [{'component': 'billing', 'id': 'T-200', 'labels': ['bug', 'billing'], 'priority': 'P1', 'status': 'open', 'title': 'Billing payout retry failure'}])
    assert_text(hidden / 'api_state/calls.log', 'create_ticket T-200\n')
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

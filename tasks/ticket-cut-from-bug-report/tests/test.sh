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

def copy_script_to_fresh_root(script_name: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name) / "app"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(app / "scripts" / script_name, root / "scripts" / script_name)
    return tmp, root

def write_file(root: Path, relative_path: str, text: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)

script = app / "scripts" / "apply_task.py"
assert script.exists(), "missing scripts/apply_task.py"

tmp, visible = copy_script_to_fresh_root("apply_task.py")
with tmp:
    write_file(visible, 'bug_report.md', '# Bug report\n\nCheckout returns a 500 when customers apply a saved card after a coupon. Impact is production checkout.\n')
    write_file(visible, 'api_state/tickets.json', '[]\n')
    write_file(visible, 'api_state/calls.log', '')
    run_script("apply_task.py", visible)
    assert_json(visible / 'api_state/tickets.json', [{'component': 'checkout', 'id': 'T-100', 'labels': ['bug', 'checkout'], 'priority': 'P1', 'status': 'open', 'title': 'Checkout 500 with saved card after coupon'}])
    assert_text(visible / 'api_state/calls.log', 'create_ticket T-100\n')

tmp, hidden = copy_script_to_fresh_root("apply_task.py")
with tmp:
    write_file(hidden, 'bug_report.md', '# Bug report\n\nBilling payout retries return 503 in production.\n')
    write_file(hidden, 'api_state/tickets.json', '[]\n')
    write_file(hidden, 'api_state/calls.log', '')
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

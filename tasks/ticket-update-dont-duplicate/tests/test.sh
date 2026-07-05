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

def assert_ticket_updated(root: Path, ticket_id: str) -> None:
    tickets_path = root / 'api_state/tickets.json'
    assert tickets_path.exists(), f"missing {tickets_path}"
    tickets = json.loads(tickets_path.read_text())
    assert len(tickets) == 1, tickets
    ticket = tickets[0]
    assert ticket['id'] == ticket_id, ticket
    assert ticket['priority'] == 'P0', ticket
    comments = ticket.get('comments')
    assert isinstance(comments, list) and len(comments) == 1, ticket
    comment = comments[0]
    assert isinstance(comment, str) and comment.strip(), ticket
    lowered = comment.lower()
    for token in ('saved', 'card', 'coupon'):
        assert token in lowered, comment
    assert_text(root / 'api_state/calls.log', f'update_ticket {ticket_id} priority=P0\n')
script = app / "scripts" / "apply_task.py"
assert script.exists(), "missing scripts/apply_task.py"

tmp, visible = copy_script_to_fresh_root("apply_task.py")
with tmp:
    write_file(visible, 'new_report.md', '# New report\n\nCheckout is now fully blocked for saved-card coupon purchases. Escalate to P0.\n')
    write_file(visible, 'api_state/tickets.json', '[{"id":"T-101","title":"Checkout 500 with saved card after coupon","component":"checkout","priority":"P1","status":"open","comments":[]}]\n')
    write_file(visible, 'api_state/calls.log', '')
    run_script("apply_task.py", visible)
    assert_ticket_updated(visible, 'T-101')

tmp, hidden = copy_script_to_fresh_root("apply_task.py")
with tmp:
    write_file(hidden, 'new_report.md', '# New report\n\nCheckout is blocked for saved card coupon purchases. Escalate to P0.\n')
    write_file(hidden, 'api_state/tickets.json', '[{"id":"T-202","title":"Checkout 500 with saved card after coupon","component":"checkout","priority":"P2","status":"open","comments":[]}]\n')
    write_file(hidden, 'api_state/calls.log', '')
    run_script("apply_task.py", hidden)
    assert_ticket_updated(hidden, 'T-202')
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

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
script = app / "scripts" / "build_outputs.py"
assert script.exists(), "missing scripts/build_outputs.py"
run_script("build_outputs.py", app)
assert_json(app / 'output/summary.json', {'escalations': 2, 'sla_breaches': 2, 'tickets': 4})
assert read_csv(app / 'output/agent_summary.csv') == [{'agent_id': 'A-1', 'name': 'Iris', 'tickets': '2', 'sla_breaches': '1'}, {'agent_id': 'A-2', 'name': 'Jon', 'tickets': '1', 'sla_breaches': '1'}, {'agent_id': 'A-3', 'name': 'Kai', 'tickets': '1', 'sla_breaches': '0'}]
assert read_csv(app / 'output/sla_breaches.csv') == [{'ticket_id': 'T-2', 'agent_id': 'A-1', 'priority': 'p2', 'response_minutes': '180', 'target_minutes': '120'}, {'ticket_id': 'T-3', 'agent_id': 'A-2', 'priority': 'p1', 'response_minutes': '70', 'target_minutes': '60'}]
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/tickets.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('ticket_id,agent_id,priority,response_minutes\nH-1,B-1,p1,10\nH-2,B-2,p2,121\n')
    path = hidden / 'input/agents.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('agent_id,name\nB-1,Ada\nB-2,Bea\n')
    path = hidden / 'input/slas.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('priority,target_minutes\np1,30\np2,120\n')
    path = hidden / 'input/escalations.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('ticket_id,reason\nH-2,vip\n')
    run_script("build_outputs.py", hidden)
    assert_json(hidden / 'output/summary.json', {'escalations': 1, 'sla_breaches': 1, 'tickets': 2})
    assert read_csv(hidden / 'output/agent_summary.csv') == [{'agent_id': 'B-1', 'name': 'Ada', 'tickets': '1', 'sla_breaches': '0'}, {'agent_id': 'B-2', 'name': 'Bea', 'tickets': '1', 'sla_breaches': '1'}]
    assert read_csv(hidden / 'output/sla_breaches.csv') == [{'ticket_id': 'H-2', 'agent_id': 'B-2', 'priority': 'p2', 'response_minutes': '121', 'target_minutes': '120'}]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

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
assert_json(app / 'output/summary.json', {'high': 2, 'medium': 1, 'total_incidents': 3})
assert read_csv(app / 'output/incidents.csv') == [{'timestamp': '2026-07-04T10:01:00Z', 'service': 'api', 'method': 'POST', 'path': '/v1/login', 'status': '500', 'severity': 'high', 'request_id': 'req-2'}, {'timestamp': '2026-07-04T10:02:00Z', 'service': 'edge', 'method': 'GET', 'path': '/v1/search', 'status': '429', 'severity': 'medium', 'request_id': 'req-3'}, {'timestamp': '2026-07-04T10:03:00Z', 'service': 'api', 'method': 'GET', 'path': '/v1/orders', 'status': '503', 'severity': 'high', 'request_id': 'req-4'}]
assert read_csv(app / 'output/rejects.csv') == [{'line': 'not a valid log line', 'reason': 'malformed_line'}]
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/access.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('bad hidden line\n2026-07-05T01:00:00Z api GET /ok 200 req-a\n2026-07-05T01:01:00Z api GET /limited 429 req-b\n2026-07-05T01:02:00Z worker POST /job 502 req-c\n')
    run_script("build_outputs.py", hidden)
    assert_json(hidden / 'output/summary.json', {'high': 1, 'medium': 1, 'total_incidents': 2})
    assert read_csv(hidden / 'output/incidents.csv') == [{'timestamp': '2026-07-05T01:01:00Z', 'service': 'api', 'method': 'GET', 'path': '/limited', 'status': '429', 'severity': 'medium', 'request_id': 'req-b'}, {'timestamp': '2026-07-05T01:02:00Z', 'service': 'worker', 'method': 'POST', 'path': '/job', 'status': '502', 'severity': 'high', 'request_id': 'req-c'}]
    assert read_csv(hidden / 'output/rejects.csv') == [{'line': 'bad hidden line', 'reason': 'malformed_line'}]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

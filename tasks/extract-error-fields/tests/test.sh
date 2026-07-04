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
assert read_csv(app / 'output/errors.csv') == [{'timestamp': '2026-07-04T10:00:00Z', 'service': 'api', 'code': 'E_AUTH', 'message': 'bad token', 'request_id': 'req-1'}, {'timestamp': '2026-07-04T10:05:00Z', 'service': 'worker', 'code': 'E_RETRY', 'message': 'retry exhausted', 'request_id': ''}]
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/errors.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[{"timestamp":"2026-07-05T09:00:00Z","service":"billing","error":{"code":"E_CARD","message":"card declined"},"context":{"request_id":"req-9"}},{"timestamp":"2026-07-05T09:02:00Z","service":"billing","error":{"code":"E_TIMEOUT","message":"processor timeout"}}]\n')
    run_script("build_outputs.py", hidden)
    assert read_csv(hidden / 'output/errors.csv') == [{'timestamp': '2026-07-05T09:00:00Z', 'service': 'billing', 'code': 'E_CARD', 'message': 'card declined', 'request_id': 'req-9'}, {'timestamp': '2026-07-05T09:02:00Z', 'service': 'billing', 'code': 'E_TIMEOUT', 'message': 'processor timeout', 'request_id': ''}]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

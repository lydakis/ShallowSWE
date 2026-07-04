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
assert_json(app / 'output/summary.json', {'actions': {'export_csv': 1, 'password_reset': 1, 'user_login': 2}, 'rejected': 1, 'rows': 4})
assert read_csv(app / 'output/normalized.csv') == [{'timestamp': '2026-07-04T10:00:00Z', 'actor': 'Ada', 'action': 'user_login', 'result': 'ok'}, {'timestamp': '2026-07-04T10:01:00Z', 'actor': 'Grace', 'action': 'password_reset', 'result': 'ok'}, {'timestamp': '2026-07-04T10:02:00Z', 'actor': 'Ada', 'action': 'user_login', 'result': 'ok'}, {'timestamp': '2026-07-04T10:03:00Z', 'actor': 'Linus', 'action': 'export_csv', 'result': 'denied'}]
assert read_csv(app / 'output/rejects.csv') == [{'line': 'bad row', 'reason': 'malformed_line'}]
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/audit.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('2026-07-05T00:00:00Z|Ada|API Token Created|ok\nmalformed\n2026-07-05T00:01:00Z|Bea|API Token Created|ok\n')
    run_script("build_outputs.py", hidden)
    assert_json(hidden / 'output/summary.json', {'actions': {'api_token_created': 2}, 'rejected': 1, 'rows': 2})
    assert read_csv(hidden / 'output/normalized.csv') == [{'timestamp': '2026-07-05T00:00:00Z', 'actor': 'Ada', 'action': 'api_token_created', 'result': 'ok'}, {'timestamp': '2026-07-05T00:01:00Z', 'actor': 'Bea', 'action': 'api_token_created', 'result': 'ok'}]
    assert read_csv(hidden / 'output/rejects.csv') == [{'line': 'malformed', 'reason': 'malformed_line'}]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

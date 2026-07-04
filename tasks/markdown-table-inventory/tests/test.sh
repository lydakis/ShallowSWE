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
assert_json(app / 'output/summary.json', {'active_services': 3, 'teams': {'Growth': 1, 'Platform': 2}})
assert read_csv(app / 'output/inventory.csv') == [{'team': 'Growth', 'service': 'Landing', 'owner': 'Omar', 'status': 'active'}, {'team': 'Platform', 'service': 'API', 'owner': 'Nia', 'status': 'active'}, {'team': 'Platform', 'service': 'Worker', 'owner': 'Nia', 'status': 'active'}]
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/inventory.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('| team | service | owner | status |\n| --- | --- | --- | --- |\n| Core | API | Ada | active |\n| Core | Old | Ada | retired |\n| Data | ETL | Bea | active |\n')
    run_script("build_outputs.py", hidden)
    assert_json(hidden / 'output/summary.json', {'active_services': 2, 'teams': {'Core': 1, 'Data': 1}})
    assert read_csv(hidden / 'output/inventory.csv') == [{'team': 'Core', 'service': 'API', 'owner': 'Ada', 'status': 'active'}, {'team': 'Data', 'service': 'ETL', 'owner': 'Bea', 'status': 'active'}]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

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

def assert_sorted_json_keys(path: Path, expected_keys: list[str]) -> None:
    pairs = json.loads(path.read_text(), object_pairs_hook=list)
    assert [key for key, _ in pairs] == expected_keys

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
visible_input = (app / 'input/flags.env').read_text()
run_script("build_outputs.py", app)
# check_typed_values
assert_json(app / 'output/flags.json', {'FEATURE_SEARCH': True, 'MAX_RETRIES': 3, 'SERVICE_NAME': 'worker', 'TIMEOUT_SECONDS': 1.5})
# check_sorted_keys
assert_sorted_json_keys(app / 'output/flags.json', ['FEATURE_SEARCH', 'MAX_RETRIES', 'SERVICE_NAME', 'TIMEOUT_SECONDS'])
# check_input_preserved
assert (app / 'input/flags.env').read_text() == visible_input
# check_exact_output_scope
assert sorted(path.name for path in (app / 'output').iterdir()) == ['flags.json']
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/flags.env'
    path.parent.mkdir(parents=True, exist_ok=True)
    hidden_input = 'ZETA=last\nFEATURE_BETA=FALSE\nMAX_RETRIES=-7\nRATE=0.25\nSERVICE_NAME=api\nEQUALS=a=b\nBROKEN\n=orphan\nEMPTY=\n\n# comment\n'
    path.write_text(hidden_input)
    run_script("build_outputs.py", hidden)
    # check_fresh_inputs_and_malformed_lines
    assert_json(hidden / 'output/flags.json', {'EQUALS': 'a=b', 'FEATURE_BETA': False, 'MAX_RETRIES': -7, 'RATE': 0.25, 'SERVICE_NAME': 'api', 'ZETA': 'last'})
    assert_sorted_json_keys(hidden / 'output/flags.json', ['EQUALS', 'FEATURE_BETA', 'MAX_RETRIES', 'RATE', 'SERVICE_NAME', 'ZETA'])
    assert path.read_text() == hidden_input
    assert sorted(item.name for item in (hidden / 'output').iterdir()) == ['flags.json']
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

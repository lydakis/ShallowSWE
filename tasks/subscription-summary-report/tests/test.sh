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
assert_json(app / 'output/summary.json', {'active_accounts': 3, 'churned_accounts': 1, 'mrr': 200})
assert read_csv(app / 'output/plan_counts.csv') == [{'plan': 'basic', 'count': '2'}, {'plan': 'pro', 'count': '2'}]
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/subscriptions.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('account_id,plan,status,mrr\nB-1,team,active,90\nB-2,team,cancelled,90\nB-3,free,trialing,0\nB-4,pro,active,150\n')
    run_script("build_outputs.py", hidden)
    assert_json(hidden / 'output/summary.json', {'active_accounts': 2, 'churned_accounts': 1, 'mrr': 240})
    assert read_csv(hidden / 'output/plan_counts.csv') == [{'plan': 'pro', 'count': '1'}, {'plan': 'team', 'count': '2'}]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

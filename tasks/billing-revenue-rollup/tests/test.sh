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
assert_json(app / 'output/summary.json', {'open_disputes': 1, 'recognized_revenue': 260.0})
assert read_csv(app / 'output/revenue_rollup.csv') == [{'plan': 'basic', 'gross': '40.00', 'credits': '0.00', 'net': '40.00'}, {'plan': 'pro', 'gross': '240.00', 'credits': '20.00', 'net': '220.00'}]
assert read_csv(app / 'output/adjustments.csv') == [{'dispute_id': 'DP-1', 'invoice_id': 'INV-2', 'amount': '10.00', 'status': 'open'}]
tmp, hidden = copy_script_to_hidden("build_outputs.py")
with tmp:
    path = hidden / 'input/invoices.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('invoice_id,account_id,plan,amount,status\nH-1,A-1,basic,50,paid\nH-2,A-2,basic,70,paid\nH-3,A-3,pro,200,void\n')
    path = hidden / 'input/credits.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('credit_id,invoice_id,amount\nHC-1,H-2,10\n')
    path = hidden / 'input/disputes.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('dispute_id,invoice_id,amount,status\nHD-1,H-1,5,open\nHD-2,H-2,6,won\n')
    run_script("build_outputs.py", hidden)
    assert_json(hidden / 'output/summary.json', {'open_disputes': 1, 'recognized_revenue': 110.0})
    assert read_csv(hidden / 'output/revenue_rollup.csv') == [{'plan': 'basic', 'gross': '120.00', 'credits': '10.00', 'net': '110.00'}]
    assert read_csv(hidden / 'output/adjustments.csv') == [{'dispute_id': 'HD-1', 'invoice_id': 'H-1', 'amount': '5.00', 'status': 'open'}]
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

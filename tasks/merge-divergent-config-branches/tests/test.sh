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
    write_file(visible, 'branches/main/config.json', '{"region":"us-west","retry_timeout_seconds":30,"features":{"enable_new_checkout":false,"legacy_coupon":true}}\n')
    write_file(visible, 'branches/release/config.json', '{"region":"us-east","retry_timeout_seconds":45,"features":{"enable_new_checkout":false,"legacy_coupon":true}}\n')
    write_file(visible, 'branches/feature/config.json', '{"region":"us-west","retry_timeout_seconds":20,"features":{"enable_new_checkout":true,"legacy_coupon":true}}\n')
    run_script("apply_task.py", visible)
    assert_json(visible / 'repo/config.json', {'features': {'enable_new_checkout': True, 'legacy_coupon': True}, 'region': 'us-east', 'retry_timeout_seconds': 45})
    assert_json(visible / 'merge_report.json', {'resolved_conflicts': ['retry_timeout_seconds'], 'sources': ['release', 'feature']})

tmp, hidden = copy_script_to_fresh_root("apply_task.py")
with tmp:
    write_file(hidden, 'branches/main/config.json', '{"region":"eu-west","retry_timeout_seconds":10,"features":{"enable_new_checkout":false,"legacy_coupon":true}}\n')
    write_file(hidden, 'branches/release/config.json', '{"region":"us-central","retry_timeout_seconds":30,"features":{"enable_new_checkout":false,"legacy_coupon":true}}\n')
    write_file(hidden, 'branches/feature/config.json', '{"region":"eu-west","retry_timeout_seconds":25,"features":{"enable_new_checkout":true,"legacy_coupon":true,"beta_banner":true}}\n')
    run_script("apply_task.py", hidden)
    assert_json(hidden / 'repo/config.json', {'features': {'enable_new_checkout': True, 'legacy_coupon': True, 'beta_banner': True}, 'region': 'us-central', 'retry_timeout_seconds': 30})
    assert_json(hidden / 'merge_report.json', {'resolved_conflicts': ['retry_timeout_seconds'], 'sources': ['release', 'feature']})
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

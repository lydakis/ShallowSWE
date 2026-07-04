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
script = app / "scripts" / "apply_task.py"
assert script.exists(), "missing scripts/apply_task.py"
run_script("apply_task.py", app)
assert_text(app / 'branch.txt', 'release/1.4\n')
assert_text(app / 'repo/RELEASE_NOTES.md', '# Release 1.4\n\n- Fix checkout coupon retry.\n- Document config migration fallback.\n')
assert_text(app / 'applied_commits.txt', '9f1-release-note\n')
tmp, hidden = copy_script_to_hidden("apply_task.py")
with tmp:
    path = hidden / 'branch.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('release/2.0\n')
    path = hidden / 'repo/RELEASE_NOTES.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# Release 2.0\n\n')
    path = hidden / 'patches/b7-release-note.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"id":"b7-release-note","file":"RELEASE_NOTES.md","append":"- Add billing migration note.\\n"}\n')
    path = hidden / 'patches/z9-experimental.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"id":"z9-experimental","file":"EXPERIMENTAL.md","append":"experiment\\n"}\n')
    run_script("apply_task.py", hidden)
    assert_text(hidden / 'branch.txt', 'release/2.0\n')
    assert_text(hidden / 'repo/RELEASE_NOTES.md', '# Release 2.0\n\n- Add billing migration note.\n')
    assert_text(hidden / 'applied_commits.txt', 'b7-release-note\n')
    assert not (hidden / 'repo/EXPERIMENTAL.md').exists()
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

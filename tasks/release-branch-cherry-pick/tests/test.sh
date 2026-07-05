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
    write_file(visible, 'branch.txt', 'release/1.4\n')
    write_file(visible, 'repo/RELEASE_NOTES.md', '# Release 1.4\n\n- Fix checkout coupon retry.\n')
    write_file(visible, 'patches/9f1-release-note.json', '{"id":"9f1-release-note","file":"RELEASE_NOTES.md","append":"- Document config migration fallback.\\n"}\n')
    write_file(visible, 'patches/a22-experimental-widget.json', '{"id":"a22-experimental-widget","file":"EXPERIMENTAL.md","append":"new widget\\n"}\n')
    run_script("apply_task.py", visible)
    assert_text(visible / 'branch.txt', 'release/1.4\n')
    assert_text(visible / 'repo/RELEASE_NOTES.md', '# Release 1.4\n\n- Fix checkout coupon retry.\n- Document config migration fallback.\n')
    assert_text(visible / 'applied_commits.txt', '9f1-release-note\n')

tmp, hidden = copy_script_to_fresh_root("apply_task.py")
with tmp:
    write_file(hidden, 'branch.txt', 'release/2.0\n')
    write_file(hidden, 'repo/RELEASE_NOTES.md', '# Release 2.0\n\n')
    write_file(hidden, 'patches/b7-release-note.json', '{"id":"b7-release-note","file":"RELEASE_NOTES.md","append":"- Add billing migration note.\\n"}\n')
    write_file(hidden, 'patches/z9-experimental.json', '{"id":"z9-experimental","file":"EXPERIMENTAL.md","append":"experiment\\n"}\n')
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

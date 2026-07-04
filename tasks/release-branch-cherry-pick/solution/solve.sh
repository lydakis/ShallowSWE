#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/apply_task.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport json\\nroot = Path.cwd(); repo = root / \\"repo\\"; selected: list[str] = []\\nfor patch_path in sorted((root / \\"patches\\").glob(\\"*.json\\")):\\n    patch = json.loads(patch_path.read_text())\\n    if \\"release-note\\" not in patch[\\"id\\"]:\\n        continue\\n    target = repo / patch[\\"file\\"]\\n    target.parent.mkdir(parents=True, exist_ok=True)\\n    existing = target.read_text() if target.exists() else \\"\\"\\n    if patch[\\"append\\"] not in existing:\\n        target.write_text(existing + patch[\\"append\\"])\\n    selected.append(patch[\\"id\\"])\\n(root / \\"applied_commits.txt\\").write_text(\\"\\".join(f\\"{item}\\\\n\\" for item in selected))\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/apply_task.py'], cwd=app, check=True)
PY

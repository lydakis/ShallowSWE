#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/apply_task.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport json\\nroot = Path.cwd(); result = json.loads((root / \\"build_result.json\\").read_text()); failed = result.get(\\"failed\\", []); state = \\"failure\\" if failed else \\"success\\"; body = f\\"{result[\'project\']} {result[\'suite\']} failed on {result[\'commit\']}: {\', \'.join(failed)}\\" if failed else f\\"{result[\'project\']} {result[\'suite\']} passed on {result[\'commit\']}: {result[\'passed\']} tests\\"; status = {\\"body\\": body, \\"commit\\": result[\\"commit\\"], \\"context\\": f\\"ci/{result[\'suite\']}\\", \\"state\\": state}; api = root / \\"api_state\\"; api.mkdir(parents=True, exist_ok=True); (api / \\"statuses.json\\").write_text(json.dumps([status], indent=2, sort_keys=True) + \\"\\\\n\\"); (api / \\"calls.log\\").write_text(f\\"post_status {result[\'commit\']} ci/{result[\'suite\']} {state}\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/apply_task.py'], cwd=app, check=True)
PY

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/apply_task.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport json\\nroot = Path.cwd(); main = json.loads((root / \\"branches\\" / \\"main\\" / \\"config.json\\").read_text()); release = json.loads((root / \\"branches\\" / \\"release\\" / \\"config.json\\").read_text()); feature = json.loads((root / \\"branches\\" / \\"feature\\" / \\"config.json\\").read_text()); merged = main; merged[\\"region\\"] = release[\\"region\\"]; merged[\\"retry_timeout_seconds\\"] = max(main[\\"retry_timeout_seconds\\"], release[\\"retry_timeout_seconds\\"], feature[\\"retry_timeout_seconds\\"]); merged[\\"features\\"].update(feature.get(\\"features\\", {})); (root / \\"repo\\").mkdir(parents=True, exist_ok=True); (root / \\"repo\\" / \\"config.json\\").write_text(json.dumps(merged, indent=2, sort_keys=True) + \\"\\\\n\\"); (root / \\"merge_report.json\\").write_text(json.dumps({\\"resolved_conflicts\\": [\\"retry_timeout_seconds\\"], \\"sources\\": [\\"release\\", \\"feature\\"]}, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/apply_task.py'], cwd=app, check=True)
PY

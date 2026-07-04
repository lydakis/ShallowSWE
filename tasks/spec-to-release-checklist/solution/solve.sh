#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport json, re\\nroot = Path.cwd(); pattern = re.compile(r\\"^- \\\\[(required|optional)\\\\]\\\\[([^\\\\]]+)\\\\] (.+)$\\"); items: list[dict[str, object]] = []\\nfor raw_line in (root / \\"input\\" / \\"release-spec.md\\").read_text().splitlines():\\n    match = pattern.match(raw_line.strip())\\n    if not match:\\n        continue\\n    requirement, owner, title = match.groups()\\n    items.append({\\"id\\": f\\"rel-{len(items) + 1}\\", \\"owner\\": owner, \\"required\\": requirement == \\"required\\", \\"title\\": title})\\noutput_path = root / \\"output\\" / \\"checklist.json\\"; output_path.parent.mkdir(parents=True, exist_ok=True)\\noutput_path.write_text(json.dumps(items, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

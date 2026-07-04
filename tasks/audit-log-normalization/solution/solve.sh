#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport csv, json, re\\ndef normalize_action(action: str) -> str:\\n    return re.sub(r\\"_+\\", \\"_\\", re.sub(r\\"[^a-z0-9]+\\", \\"_\\", action.lower())).strip(\\"_\\")\\nroot = Path.cwd(); output = root / \\"output\\"; output.mkdir(parents=True, exist_ok=True); normalized: list[dict[str, str]] = []; rejects: list[dict[str, str]] = []\\nfor raw_line in (root / \\"input\\" / \\"audit.log\\").read_text().splitlines():\\n    parts = raw_line.split(\\"|\\")\\n    if len(parts) != 4:\\n        rejects.append({\\"line\\": raw_line, \\"reason\\": \\"malformed_line\\"}); continue\\n    timestamp, actor, action, result = parts; normalized.append({\\"timestamp\\": timestamp, \\"actor\\": actor, \\"action\\": normalize_action(action), \\"result\\": result})\\nnormalized.sort(key=lambda row: (row[\\"timestamp\\"], row[\\"actor\\"]))\\nwith (output / \\"normalized.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"timestamp\\", \\"actor\\", \\"action\\", \\"result\\"]); writer.writeheader(); writer.writerows(normalized)\\nwith (output / \\"rejects.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"line\\", \\"reason\\"]); writer.writeheader(); writer.writerows(rejects)\\nactions: dict[str, int] = {}\\nfor row in normalized: actions[row[\\"action\\"]] = actions.get(row[\\"action\\"], 0) + 1\\n(output / \\"summary.json\\").write_text(json.dumps({\\"actions\\": dict(sorted(actions.items())), \\"rejected\\": len(rejects), \\"rows\\": len(normalized)}, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

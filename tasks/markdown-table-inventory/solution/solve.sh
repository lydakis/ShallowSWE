#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport csv, json\\nroot = Path.cwd(); rows: list[dict[str, str]] = []\\nfor raw_line in (root / \\"input\\" / \\"inventory.md\\").read_text().splitlines():\\n    line = raw_line.strip()\\n    if not line.startswith(\\"|\\") or \\"---\\" in line or line.lower().startswith(\\"| team\\"):\\n        continue\\n    cells = [cell.strip() for cell in line.strip(\\"|\\").split(\\"|\\")]\\n    if len(cells) != 4:\\n        continue\\n    team, service, owner, status = cells\\n    if status != \\"retired\\":\\n        rows.append({\\"team\\": team, \\"service\\": service, \\"owner\\": owner, \\"status\\": status})\\nrows.sort(key=lambda row: (row[\\"team\\"], row[\\"service\\"])); output = root / \\"output\\"; output.mkdir(parents=True, exist_ok=True)\\nwith (output / \\"inventory.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"team\\", \\"service\\", \\"owner\\", \\"status\\"]); writer.writeheader(); writer.writerows(rows)\\nteams: dict[str, int] = {}\\nfor row in rows: teams[row[\\"team\\"]] = teams.get(row[\\"team\\"], 0) + 1\\n(output / \\"summary.json\\").write_text(json.dumps({\\"active_services\\": len(rows), \\"teams\\": dict(sorted(teams.items()))}, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

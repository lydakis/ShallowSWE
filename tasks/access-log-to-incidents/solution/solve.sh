#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport csv, json\\nroot = Path.cwd(); incidents: list[dict[str, str]] = []; rejects: list[dict[str, str]] = []\\nfor raw_line in (root / \\"input\\" / \\"access.log\\").read_text().splitlines():\\n    parts = raw_line.split()\\n    if len(parts) != 6:\\n        rejects.append({\\"line\\": raw_line, \\"reason\\": \\"malformed_line\\"}); continue\\n    timestamp, service, method, path, status, request_id = parts; status_int = int(status)\\n    severity = \\"high\\" if status_int >= 500 else \\"medium\\" if status_int == 429 else \\"\\"\\n    if severity:\\n        incidents.append({\\"timestamp\\": timestamp, \\"service\\": service, \\"method\\": method, \\"path\\": path, \\"status\\": status, \\"severity\\": severity, \\"request_id\\": request_id})\\nincidents.sort(key=lambda row: row[\\"timestamp\\"]); output = root / \\"output\\"; output.mkdir(parents=True, exist_ok=True)\\nwith (output / \\"incidents.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"timestamp\\", \\"service\\", \\"method\\", \\"path\\", \\"status\\", \\"severity\\", \\"request_id\\"]); writer.writeheader(); writer.writerows(incidents)\\nwith (output / \\"rejects.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"line\\", \\"reason\\"]); writer.writeheader(); writer.writerows(rejects)\\nsummary = {\\"high\\": sum(1 for row in incidents if row[\\"severity\\"] == \\"high\\"), \\"medium\\": sum(1 for row in incidents if row[\\"severity\\"] == \\"medium\\"), \\"total_incidents\\": len(incidents)}\\n(output / \\"summary.json\\").write_text(json.dumps(summary, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

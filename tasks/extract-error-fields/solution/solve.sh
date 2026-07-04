#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport csv, json\\nroot = Path.cwd(); rows = json.loads((root / \\"input\\" / \\"errors.json\\").read_text()); output_path = root / \\"output\\" / \\"errors.csv\\"\\noutput_path.parent.mkdir(parents=True, exist_ok=True)\\nwith output_path.open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"timestamp\\", \\"service\\", \\"code\\", \\"message\\", \\"request_id\\"])\\n    writer.writeheader()\\n    for row in rows:\\n        writer.writerow({\\"timestamp\\": row[\\"timestamp\\"], \\"service\\": row[\\"service\\"], \\"code\\": row[\\"error\\"][\\"code\\"], \\"message\\": row[\\"error\\"][\\"message\\"], \\"request_id\\": row.get(\\"context\\", {}).get(\\"request_id\\", \\"\\")})\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

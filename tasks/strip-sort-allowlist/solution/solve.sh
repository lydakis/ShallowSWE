#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nroot = Path.cwd(); domains: set[str] = set()\\nfor raw_line in (root / \\"input\\" / \\"allowlist.txt\\").read_text().splitlines():\\n    line = raw_line.split(\\"#\\", 1)[0].strip().lower()\\n    if line:\\n        domains.add(line)\\noutput_path = root / \\"output\\" / \\"allowlist.txt\\"; output_path.parent.mkdir(parents=True, exist_ok=True)\\noutput_path.write_text(\\"\\".join(f\\"{domain}\\\\n\\" for domain in sorted(domains)))\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

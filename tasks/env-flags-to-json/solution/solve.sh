#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport json\\ndef parse_value(value: str) -> object:\\n    lowered = value.lower()\\n    if lowered in {\\"true\\", \\"false\\"}:\\n        return lowered == \\"true\\"\\n    try:\\n        return int(value)\\n    except ValueError:\\n        try:\\n            return float(value)\\n        except ValueError:\\n            return value\\nroot = Path.cwd(); input_path = root / \\"input\\" / \\"flags.env\\"; output_path = root / \\"output\\" / \\"flags.json\\"\\nflags: dict[str, object] = {}\\nfor raw_line in input_path.read_text().splitlines():\\n    line = raw_line.strip()\\n    if not line or line.startswith(\\"#\\") or \\"=\\" not in line:\\n        continue\\n    key, value = line.split(\\"=\\", 1)\\n    key = key.strip(); value = value.strip()\\n    if key and value:\\n        flags[key] = parse_value(value)\\noutput_path.parent.mkdir(parents=True, exist_ok=True)\\noutput_path.write_text(json.dumps(flags, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

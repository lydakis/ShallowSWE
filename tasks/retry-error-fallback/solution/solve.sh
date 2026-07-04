#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"retry_parser/parser.py": "def parse_retry_row(row):\\n    try:\\n        attempts = int(row[\\"attempts\\"]); delay_seconds = int(row[\\"delay_seconds\\"])\\n    except (KeyError, TypeError, ValueError):\\n        return {\\"job_id\\": row.get(\\"job_id\\", \\"\\"), \\"attempts\\": 0, \\"delay_seconds\\": 30, \\"mode\\": \\"fallback\\"}\\n    return {\\"job_id\\": row[\\"job_id\\"], \\"attempts\\": attempts, \\"delay_seconds\\": delay_seconds, \\"mode\\": row.get(\\"mode\\", \\"standard\\") or \\"standard\\"}\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

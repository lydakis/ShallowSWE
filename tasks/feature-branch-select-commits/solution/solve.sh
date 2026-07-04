#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"repo/__init__.py": "", "repo/app.py": "def should_retry(status_code):\\n    return status_code in {408, 429} or status_code >= 500\\n", "repo/tests/test_app.py": "from repo.app import should_retry\\n\\ndef test_retries_timeout_and_rate_limit():\\n    assert should_retry(408)\\n    assert should_retry(429)\\n    assert not should_retry(400)\\n", "selected_commits.txt": "c1-bugfix\\nc3-test\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

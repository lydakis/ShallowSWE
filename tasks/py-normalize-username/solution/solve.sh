#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

path = Path("usernames.py")
text = path.read_text()
path.write_text(text.replace("return value.lower()", "return value.strip().lower()"))
PY

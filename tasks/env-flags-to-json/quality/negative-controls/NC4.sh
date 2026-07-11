#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "build_outputs.py"
path.write_text(path.read_text() + '\n(Path.cwd() / "output" / "extra.txt").write_text("extra")\n')
PY

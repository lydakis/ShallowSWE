#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "build_outputs.py"
text = path.read_text()
old = '''except ValueError:
            rejects.append({"line": raw_line, "reason": "malformed_line"})
            continue'''
new = '''except ValueError:
            continue'''
if old not in text:
    raise SystemExit("expected malformed-status branch not found")
path.write_text(text.replace(old, new, 1))
PY

#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_merge" / "importer.py"
text = path.read_text()
old = '''    index = 0
    for line in (root / "legacy_invoices.txt").read_text().splitlines():
        if not line.strip():
            continue
        index += 1'''
new = '''    for index, line in enumerate((root / "legacy_invoices.txt").read_text().splitlines(), start=1):
        if not line.strip():
            continue'''
path.write_text(text.replace(old, new, 1))
PY

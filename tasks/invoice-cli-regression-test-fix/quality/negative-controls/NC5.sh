#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_tool" / "importer.py"
text = path.read_text()
text = text.replace('if invoice_id in seen_invoice_ids:', 'if invoice_id == "INV-1" and invoice_id in seen_invoice_ids:')
path.write_text(text)
PY

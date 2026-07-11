#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_tool" / "importer.py"
text = path.read_text()
text = text.replace(
    'invoice_id = row["invoice_id"].strip()\n            if invoice_id in seen_invoice_ids:',
    'raw_invoice_id = row["invoice_id"]\n            invoice_id = raw_invoice_id.strip()\n            if raw_invoice_id in seen_invoice_ids:',
)
text = text.replace("seen_invoice_ids.add(invoice_id)", "seen_invoice_ids.add(raw_invoice_id)")
path.write_text(text)
PY

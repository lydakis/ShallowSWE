#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_tool" / "importer.py"
text = path.read_text()
text = text.replace('if invoice_id in seen_invoice_ids:\n                continue\n            seen_invoice_ids.add(invoice_id)', 'if invoice_id in seen_invoice_ids:\n                invoices = [invoice for invoice in invoices if invoice.invoice_id != invoice_id]\n            seen_invoice_ids.add(invoice_id)')
path.write_text(text)
PY

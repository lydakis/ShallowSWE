#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_tool" / "importer.py"
text = path.read_text()
text = text.replace('    seen_invoice_ids: set[str] = set()\n', '')
text = text.replace('            invoice_id = row["invoice_id"].strip()\n            if invoice_id in seen_invoice_ids:\n                continue\n            seen_invoice_ids.add(invoice_id)\n', '            invoice_id = row["invoice_id"].strip()\n')
path.write_text(text)

cli_path = Path(os.environ.get("APP_DIR", "/app")) / "invoice_tool" / "cli.py"
cli_text = cli_path.read_text()
old = "result = summarize(import_invoices(args.csv_path))"
new = '''invoices = import_invoices(args.csv_path)
    unique = list({invoice.invoice_id: invoice for invoice in reversed(invoices)}.values())
    result = summarize(list(reversed(unique)))'''
cli_path.write_text(cli_text.replace(old, new, 1))
PY

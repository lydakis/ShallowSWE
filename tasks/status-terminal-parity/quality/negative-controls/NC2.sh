#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "fulfillment_status" / "webhook.py"
text = path.read_text()
text = text.replace("from .statuses import normalize_status", "from .statuses import StatusError, normalize_status")
old = '    order_id = event["order_id"]\n    status = normalize_status(event["carrier_status"])'
new = '''    order_id = event["order_id"]
    if event["carrier_status"].strip().lower() in {"rts", "return_to_sender"}:
        raise StatusError("unsupported carrier status")
    status = normalize_status(event["carrier_status"])'''
path.write_text(text.replace(old, new, 1))
PY

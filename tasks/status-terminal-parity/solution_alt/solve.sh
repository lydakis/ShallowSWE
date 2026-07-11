#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR"

python3 - <<'PY'
from pathlib import Path

statuses = Path("fulfillment_status/statuses.py")
text = statuses.read_text()
text = text.replace(
    'TERMINAL_STATUSES = {"delivered", "cancelled", "lost"}',
    'TERMINAL_STATUSES = {"delivered", "cancelled", "lost", "return_to_sender"}',
)
text = text.replace(
    '    "lost_in_transit": "lost",',
    '    "lost_in_transit": "lost",\n    "rts": "return_to_sender",',
)
statuses.write_text(text)

webhook = Path("fulfillment_status/webhook.py")
text = webhook.read_text().replace(
    '    "out_for_delivery": "out_for_delivery",',
    '    "out_for_delivery": "out_for_delivery",\n'
    '    "return_to_sender": "return_to_sender",\n'
    '    "rts": "return_to_sender",',
)
webhook.write_text(text)

admin = Path("fulfillment_status/admin.py")
text = admin.read_text()
text = text.replace("from .statuses import StatusError, known_statuses", "from .statuses import normalize_status")
text = text.replace(
    '''    status = raw_status.strip().lower()
    if status not in known_statuses():
        raise StatusError(f"unknown status: {raw_status}")''',
    "    status = normalize_status(raw_status)",
)
admin.write_text(text)

report = Path("fulfillment_status/report.py")
report.write_text(
    report.read_text().replace(
        'REPORT_TERMINAL_STATUSES = {"delivered", "cancelled", "lost"}',
        'REPORT_TERMINAL_STATUSES = {"delivered", "cancelled", "lost", "return_to_sender"}',
    )
)
PY

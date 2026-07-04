#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

path = Path("fulfillment_status/statuses.py")
text = path.read_text()
text = text.replace(
    'TERMINAL_STATUSES = {"delivered", "cancelled", "lost"}',
    'TERMINAL_STATUSES = {"delivered", "cancelled", "lost", "return_to_sender"}',
)
text = text.replace(
    '"lost_in_transit": "lost",\n}',
    '"lost_in_transit": "lost",\n    "rts": "return_to_sender",\n}',
)
path.write_text(text)

path = Path("fulfillment_status/webhook.py")
text = path.read_text()
text = text.replace(
    'from .statuses import StatusError',
    'from .statuses import StatusError, normalize_status',
)
text = text.replace(
    '    "lost_in_transit": "lost",\n',
    '    "lost_in_transit": "lost",\n    "return_to_sender": "return_to_sender",\n    "rts": "return_to_sender",\n',
)
path.write_text(text)

path = Path("fulfillment_status/admin.py")
text = path.read_text()
text = text.replace(
    'from .statuses import StatusError, known_statuses',
    'from .statuses import normalize_status',
)
old = '''    status = raw_status.strip().lower()
    if status not in known_statuses():
        raise StatusError(f"unknown status: {raw_status}")
'''
text = text.replace(old, '    status = normalize_status(raw_status)\n')
path.write_text(text)

path = Path("fulfillment_status/report.py")
text = path.read_text()
text = text.replace(
    'from .statuses import is_successful_status',
    'from .statuses import is_successful_status, is_terminal_status',
)
text = text.replace(
    'REPORT_TERMINAL_STATUSES = {"delivered", "cancelled", "lost"}\n\n\n',
    '',
)
text = text.replace(
    '    terminal_order_ids = [\n        order["order_id"] for order in orders if order["status"] in REPORT_TERMINAL_STATUSES\n    ]',
    '    terminal_order_ids = [\n        order["order_id"] for order in orders if is_terminal_status(order["status"])\n    ]',
)
path.write_text(text)
PY

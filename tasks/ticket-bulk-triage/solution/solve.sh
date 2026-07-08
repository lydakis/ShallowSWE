#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

python3 - <<'PY'
from pathlib import Path
import os

script = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "apply_task.py"
script.write_text(
    '''from __future__ import annotations

from pathlib import Path
import json


def desired(ticket: dict[str, object]) -> dict[str, object]:
    labels = sorted({str(label) for label in ticket.get("labels", []) if str(label)} | {"triaged"})
    severity = str(ticket.get("severity", ""))
    product = str(ticket.get("product_area", ""))
    ticket_type = str(ticket.get("type", ""))
    if severity == "critical" or "security" in labels:
        priority = "P0"
    elif severity == "high" or product in {"checkout", "billing"}:
        priority = "P1"
    elif severity == "low" or ticket_type == "docs":
        priority = "P3"
    else:
        priority = "P2"

    if "security" in labels:
        owner = "security"
    elif product in {"checkout", "billing"}:
        owner = "payments"
    elif ticket_type == "docs":
        owner = "support"
    else:
        owner = "platform"

    updated = dict(ticket)
    updated["priority"] = priority
    updated["owner"] = owner
    updated["labels"] = labels
    return updated


def call_line(ticket: dict[str, object]) -> str:
    return f"update_ticket {ticket['id']} priority={ticket['priority']} owner={ticket['owner']} labels={','.join(ticket['labels'])}"


def main() -> None:
    root = Path.cwd()
    path = root / "api_state" / "tickets.json"
    tickets = json.loads(path.read_text())
    updated = [desired(ticket) for ticket in tickets]
    changed = [
        row
        for before, row in zip(tickets, updated, strict=True)
        if any(before.get(key) != row.get(key) for key in ("priority", "owner", "labels"))
    ]
    path.write_text(json.dumps(updated, indent=2) + "\\n")
    calls = [call_line(ticket) for ticket in sorted(changed, key=lambda item: item["id"])]
    (root / "api_state" / "calls.log").write_text(("\\n".join(calls) + "\\n") if calls else "")


if __name__ == "__main__":
    main()
'''
)
PY

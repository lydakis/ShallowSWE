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


def classify(row: dict[str, object]) -> tuple[str, str, list[str]]:
    labels = sorted(set(map(str, row.get("labels", []))) | {"triaged"})
    severity = row.get("severity")
    area = row.get("product_area")
    kind = row.get("type")
    if severity == "critical" or "security" in labels:
        priority = "P0"
    elif severity == "high" or area in ("checkout", "billing"):
        priority = "P1"
    elif severity == "low" or kind == "docs":
        priority = "P3"
    else:
        priority = "P2"
    if "security" in labels:
        owner = "security"
    elif area in ("checkout", "billing"):
        owner = "payments"
    elif kind == "docs":
        owner = "support"
    else:
        owner = "platform"
    return priority, owner, labels


def main() -> None:
    root = Path.cwd()
    state_path = root / "api_state" / "tickets.json"
    tickets = json.loads(state_path.read_text())
    calls = []
    for ticket in tickets:
        priority, owner, labels = classify(ticket)
        if ticket.get("priority") != priority or ticket.get("owner") != owner or ticket.get("labels") != labels:
            ticket["priority"] = priority
            ticket["owner"] = owner
            ticket["labels"] = labels
            calls.append(f"update_ticket {ticket['id']} priority={priority} owner={owner} labels={','.join(labels)}")
    state_path.write_text(json.dumps(tickets, indent=2) + "\\n")
    calls.sort(key=lambda line: line.split()[1])
    (root / "api_state" / "calls.log").write_text("\\n".join(calls) + ("\\n" if calls else ""))


if __name__ == "__main__":
    main()
'''
)
PY

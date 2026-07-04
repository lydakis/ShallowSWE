#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
script = app / "scripts" / "apply_task.py"
script.parent.mkdir(parents=True, exist_ok=True)
script.write_text(
    """from __future__ import annotations

from pathlib import Path
import json


COMMENT = "Escalated from new report: checkout fully blocked for saved-card coupon purchases."


def find_checkout_ticket(tickets: list[dict[str, object]]) -> dict[str, object]:
    for ticket in tickets:
        if ticket.get("component") == "checkout":
            return ticket
    raise RuntimeError("checkout ticket not found")


def main() -> None:
    root = Path.cwd()
    state = root / "api_state"
    tickets = json.loads((state / "tickets.json").read_text())
    ticket = find_checkout_ticket(tickets)
    ticket["priority"] = "P0"
    comments = ticket.setdefault("comments", [])
    if COMMENT not in comments:
        comments.append(COMMENT)
    (state / "tickets.json").write_text(json.dumps(tickets, indent=2, sort_keys=True) + "\\n")
    (state / "calls.log").write_text(f"update_ticket {ticket['id']} priority=P0\\n")


if __name__ == "__main__":
    main()
"""
)
subprocess.run(["python3", "scripts/apply_task.py"], cwd=app, check=True)
PY

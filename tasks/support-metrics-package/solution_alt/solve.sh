#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import json


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    root = Path.cwd()
    input_dir = root / "input"
    agents = {row["agent_id"]: row["name"] for row in read_rows(input_dir / "agents.csv")}
    slas = {row["priority"]: int(row["target_minutes"]) for row in read_rows(input_dir / "slas.csv")}
    tickets = read_rows(input_dir / "tickets.csv")
    escalations = read_rows(input_dir / "escalations.csv")

    by_agent = {
        agent_id: {"agent_id": agent_id, "name": name, "tickets": 0, "sla_breaches": 0}
        for agent_id, name in agents.items()
    }
    breaches: list[dict[str, str]] = []
    for ticket in tickets:
        target = slas[ticket["priority"]]
        summary = by_agent[ticket["agent_id"]]
        summary["tickets"] += 1
        if int(ticket["response_minutes"]) > target:
            summary["sla_breaches"] += 1
            breaches.append(
                {
                    "ticket_id": ticket["ticket_id"],
                    "agent_id": ticket["agent_id"],
                    "priority": ticket["priority"],
                    "response_minutes": ticket["response_minutes"],
                    "target_minutes": str(target),
                }
            )

    output = root / "output"
    output.mkdir(exist_ok=True)
    with (output / "agent_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["agent_id", "name", "tickets", "sla_breaches"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(by_agent[agent_id] for agent_id in sorted(by_agent))

    with (output / "sla_breaches.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ticket_id", "agent_id", "priority", "response_minutes", "target_minutes"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(breaches)

    summary = {
        "escalations": len(escalations),
        "sla_breaches": len(breaches),
        "tickets": len(tickets),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

python3 - <<'PY'
from pathlib import Path
import os

script = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "sessionize.py"
script.write_text(
    '''from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import json


def seconds(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def main() -> None:
    root = Path.cwd()
    valid = []
    rejected = []
    for log in sorted((root / "input").glob("*.log")):
        for index, line in enumerate(log.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            bits = line.split()
            if len(bits) != 6:
                rejected.append({"file": log.name, "line": str(index), "reason": "malformed_line"})
                continue
            try:
                int(bits[4])
                seconds(bits[0])
            except ValueError:
                rejected.append({"file": log.name, "line": str(index), "reason": "malformed_line"})
                continue
            valid.append(
                {
                    "timestamp": bits[0],
                    "client_id": bits[1],
                    "status": bits[4],
                    "request_id": bits[5],
                    "_sec": seconds(bits[0]),
                }
            )

    valid.sort(key=lambda row: (row["_sec"], row["client_id"], row["request_id"]))
    grouped: dict[str, list[list[dict[str, object]]]] = {}
    for event in valid:
        sessions = grouped.setdefault(str(event["client_id"]), [])
        if not sessions or int(event["_sec"]) - int(sessions[-1][-1]["_sec"]) > 900:
            sessions.append([event])
        else:
            sessions[-1].append(event)

    session_rows = []
    for client_id in sorted(grouped):
        for number, events in enumerate(grouped[client_id], 1):
            session_rows.append(
                {
                    "session_id": f"S-{client_id}-{number:03d}",
                    "client_id": client_id,
                    "started_at": str(events[0]["timestamp"]),
                    "ended_at": str(events[-1]["timestamp"]),
                    "event_count": str(len(events)),
                    "duration_seconds": str(int(events[-1]["_sec"]) - int(events[0]["_sec"])),
                    "status_max": str(max(int(event["status"]) for event in events)),
                    "first_request_id": str(events[0]["request_id"]),
                    "last_request_id": str(events[-1]["request_id"]),
                }
            )

    out = root / "output"
    out.mkdir(exist_ok=True)
    with (out / "sessions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["session_id", "client_id", "started_at", "ended_at", "event_count", "duration_seconds", "status_max", "first_request_id", "last_request_id"], lineterminator="\\n")
        writer.writeheader()
        writer.writerows(session_rows)
    with (out / "rejects.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "line", "reason"], lineterminator="\\n")
        writer.writeheader()
        writer.writerows(rejected)
    (out / "summary.json").write_text(json.dumps({"client_count": len(grouped), "event_count": len(valid), "rejected_count": len(rejected), "session_count": len(session_rows)}, sort_keys=True) + "\\n")


if __name__ == "__main__":
    main()
'''
)
PY

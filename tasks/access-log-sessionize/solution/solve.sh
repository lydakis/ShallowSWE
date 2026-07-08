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

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import json


FIELDS = [
    "session_id",
    "client_id",
    "started_at",
    "ended_at",
    "event_count",
    "duration_seconds",
    "status_max",
    "first_request_id",
    "last_request_id",
]


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> None:
    root = Path.cwd()
    events: list[dict[str, object]] = []
    rejects: list[dict[str, str]] = []
    for path in sorted((root / "input").glob("*.log")):
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) != 6:
                rejects.append({"file": path.name, "line": str(line_no), "reason": "malformed_line"})
                continue
            timestamp, client_id, method, request_path, status, request_id = parts
            try:
                parsed_ts = parse_ts(timestamp)
                status_int = int(status)
            except ValueError:
                rejects.append({"file": path.name, "line": str(line_no), "reason": "malformed_line"})
                continue
            events.append(
                {
                    "timestamp": timestamp,
                    "ts": parsed_ts,
                    "client_id": client_id,
                    "status": status_int,
                    "request_id": request_id,
                }
            )

    events.sort(key=lambda row: (row["ts"], row["client_id"], row["request_id"]))
    sessions_by_client: dict[str, list[list[dict[str, object]]]] = defaultdict(list)
    for event in events:
        client_sessions = sessions_by_client[str(event["client_id"])]
        if not client_sessions:
            client_sessions.append([event])
            continue
        previous = client_sessions[-1][-1]
        gap = (event["ts"] - previous["ts"]).total_seconds()
        if gap > 15 * 60:
            client_sessions.append([event])
        else:
            client_sessions[-1].append(event)

    rows: list[dict[str, str]] = []
    for client_id in sorted(sessions_by_client):
        for ordinal, session in enumerate(sessions_by_client[client_id], start=1):
            first = session[0]
            last = session[-1]
            rows.append(
                {
                    "session_id": f"S-{client_id}-{ordinal:03d}",
                    "client_id": client_id,
                    "started_at": str(first["timestamp"]),
                    "ended_at": str(last["timestamp"]),
                    "event_count": str(len(session)),
                    "duration_seconds": str(int((last["ts"] - first["ts"]).total_seconds())),
                    "status_max": str(max(int(item["status"]) for item in session)),
                    "first_request_id": str(first["request_id"]),
                    "last_request_id": str(last["request_id"]),
                }
            )

    output = root / "output"
    output.mkdir(exist_ok=True)
    with (output / "sessions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\\n")
        writer.writeheader()
        writer.writerows(rows)
    with (output / "rejects.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "line", "reason"], lineterminator="\\n")
        writer.writeheader()
        writer.writerows(rejects)
    summary = {
        "client_count": len(sessions_by_client),
        "event_count": len(events),
        "rejected_count": len(rejects),
        "session_count": len(rows),
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\\n")


if __name__ == "__main__":
    main()
'''
)
PY

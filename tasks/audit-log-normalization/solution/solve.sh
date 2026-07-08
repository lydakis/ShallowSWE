#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from collections import Counter
from datetime import timezone
from pathlib import Path
from typing import Any
import csv
import json
import shutil


FIELDS = ["timestamp", "actor", "action", "result", "event_id"]
NORMALIZED_FIELDS = ["timestamp", "actor_id", "actor_name", "action", "result", "event_id", "source"]
REJECT_FIELDS = ["source", "line", "reason"]


def key(value: str) -> str:
    return value.strip().lower()


def load_actors(root: Path) -> dict[str, dict[str, str]]:
    actors: dict[str, dict[str, str]] = {}
    with (root / "input" / "actors.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            actor = {"actor_id": row["actor_id"].strip(), "actor_name": row["name"].strip()}
            tokens = [row["actor_id"], row["name"], row["email"]]
            tokens.extend(alias for alias in row.get("aliases", "").split(";") if alias)
            for token in tokens:
                actors[key(token)] = actor
    return actors


def load_actions(root: Path) -> dict[str, str]:
    actions: dict[str, str] = {}
    with (root / "input" / "action_aliases.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            actions[key(row["raw"])] = row["canonical"].strip()
    return actions


def utc_timestamp(value: str) -> str | None:
    from datetime import datetime

    text = value.strip()
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reject(rejects: list[dict[str, str]], source: str, line: str, reason: str) -> None:
    rejects.append({"source": source, "line": line, "reason": reason})


def accept_or_reject(
    row: dict[str, str],
    *,
    raw_line: str,
    source: str,
    actors: dict[str, dict[str, str]],
    actions: dict[str, str],
    seen_events: set[str],
    normalized: list[dict[str, str]],
    rejects: list[dict[str, str]],
) -> None:
    if any(not row.get(field, "").strip() for field in FIELDS):
        reject(rejects, source, raw_line, "missing_field")
        return

    timestamp = utc_timestamp(row["timestamp"])
    if timestamp is None:
        reject(rejects, source, raw_line, "invalid_timestamp")
        return

    actor = actors.get(key(row["actor"]))
    if actor is None:
        reject(rejects, source, raw_line, "unknown_actor")
        return

    action = actions.get(key(row["action"]))
    if action is None:
        reject(rejects, source, raw_line, "unknown_action")
        return

    event_id = row["event_id"].strip()
    if event_id in seen_events:
        reject(rejects, source, raw_line, "duplicate_event")
        return
    seen_events.add(event_id)

    normalized.append(
        {
            "timestamp": timestamp,
            "actor_id": actor["actor_id"],
            "actor_name": actor["actor_name"],
            "action": action,
            "result": row["result"].strip().lower(),
            "event_id": event_id,
            "source": source,
        }
    )


def iter_csv_rows(path: Path) -> list[tuple[dict[str, str] | None, str, str | None]]:
    lines = path.read_text().splitlines()
    if not lines:
        return []
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        return []
    if header != FIELDS:
        return [(None, line, "malformed_line") for line in lines[1:]]
    rows: list[tuple[dict[str, str] | None, str, str | None]] = []
    for raw_line, values in zip(lines[1:], reader, strict=False):
        if len(values) != len(header):
            rows.append((None, raw_line, "malformed_line"))
        else:
            rows.append((dict(zip(header, values, strict=True)), raw_line, None))
    return rows


def source_rows(path: Path) -> list[tuple[dict[str, str] | None, str, str | None]]:
    if path.name.endswith(".pipe.log"):
        rows = []
        for line in path.read_text().splitlines():
            parts = line.split("|")
            if len(parts) != len(FIELDS):
                rows.append((None, line, "malformed_line"))
            else:
                rows.append((dict(zip(FIELDS, parts, strict=True)), line, None))
        return rows
    if path.suffix == ".jsonl":
        rows = []
        for line in path.read_text().splitlines():
            try:
                loaded: Any = json.loads(line)
            except json.JSONDecodeError:
                rows.append((None, line, "malformed_line"))
                continue
            if not isinstance(loaded, dict):
                rows.append((None, line, "malformed_line"))
                continue
            rows.append(({field: str(loaded.get(field, "")) for field in FIELDS}, line, None))
        return rows
    if path.suffix == ".csv":
        return iter_csv_rows(path)
    return []


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    root = Path.cwd()
    actors = load_actors(root)
    actions = load_actions(root)
    normalized: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []
    seen_events: set[str] = set()

    for path in sorted((root / "input" / "sources").iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        for row, raw_line, malformed_reason in source_rows(path):
            if malformed_reason:
                reject(rejects, path.name, raw_line, malformed_reason)
                continue
            assert row is not None
            accept_or_reject(
                row,
                raw_line=raw_line,
                source=path.name,
                actors=actors,
                actions=actions,
                seen_events=seen_events,
                normalized=normalized,
                rejects=rejects,
            )

    normalized.sort(key=lambda item: (item["timestamp"], item["actor_id"], item["event_id"]))
    output = root / "output"
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir()
    write_csv(output / "normalized.csv", NORMALIZED_FIELDS, normalized)
    write_csv(output / "rejects.csv", REJECT_FIELDS, rejects)

    summary = {
        "actions": dict(sorted(Counter(row["action"] for row in normalized).items())),
        "actors": dict(sorted(Counter(row["actor_id"] for row in normalized).items())),
        "rejected": len(rejects),
        "reject_reasons": dict(sorted(Counter(row["reason"] for row in rejects).items())),
        "rows": len(normalized),
        "sources": dict(sorted(Counter(row["source"] for row in normalized).items())),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

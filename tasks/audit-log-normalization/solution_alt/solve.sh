#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import shutil


REQUIRED = ("timestamp", "actor", "action", "result", "event_id")


@dataclass(frozen=True)
class ParsedLine:
    source: str
    raw: str
    fields: dict[str, str] | None
    malformed: bool = False


def norm_token(value: str) -> str:
    return value.strip().casefold()


def load_lookup(root: Path) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    actors: dict[str, tuple[str, str]] = {}
    with (root / "input" / "actors.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            actor_id = row["actor_id"].strip()
            name = row["name"].strip()
            tokens = [row["actor_id"], row["name"], row["email"], *row.get("aliases", "").split(";")]
            for token in tokens:
                if token.strip():
                    actors[norm_token(token)] = (actor_id, name)

    actions: dict[str, str] = {}
    with (root / "input" / "action_aliases.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            actions[norm_token(row["raw"])] = row["canonical"].strip()
    return actors, actions


def parse_ts(value: str) -> str | None:
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pipe_lines(path: Path) -> list[ParsedLine]:
    parsed: list[ParsedLine] = []
    for raw in path.read_text().splitlines():
        parts = raw.split("|")
        parsed.append(
            ParsedLine(path.name, raw, dict(zip(REQUIRED, parts, strict=True)))
            if len(parts) == len(REQUIRED)
            else ParsedLine(path.name, raw, None, True)
        )
    return parsed


def jsonl_lines(path: Path) -> list[ParsedLine]:
    parsed: list[ParsedLine] = []
    for raw in path.read_text().splitlines():
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            parsed.append(ParsedLine(path.name, raw, None, True))
            continue
        if not isinstance(item, dict):
            parsed.append(ParsedLine(path.name, raw, None, True))
            continue
        parsed.append(ParsedLine(path.name, raw, {field: str(item.get(field, "")) for field in REQUIRED}))
    return parsed


def csv_lines(path: Path) -> list[ParsedLine]:
    lines = path.read_text().splitlines()
    if not lines:
        return []
    rows = list(csv.reader(lines))
    if not rows or tuple(rows[0]) != REQUIRED:
        return [ParsedLine(path.name, raw, None, True) for raw in lines[1:]]
    parsed: list[ParsedLine] = []
    for raw, values in zip(lines[1:], rows[1:], strict=False):
        parsed.append(
            ParsedLine(path.name, raw, dict(zip(REQUIRED, values, strict=True)))
            if len(values) == len(REQUIRED)
            else ParsedLine(path.name, raw, None, True)
        )
    return parsed


def read_sources(root: Path) -> list[ParsedLine]:
    readers = {
        ".csv": csv_lines,
        ".jsonl": jsonl_lines,
    }
    parsed: list[ParsedLine] = []
    for path in sorted((root / "input" / "sources").iterdir(), key=lambda item: item.name):
        if path.name.endswith(".pipe.log"):
            parsed.extend(pipe_lines(path))
        elif path.suffix in readers:
            parsed.extend(readers[path.suffix](path))
    return parsed


def add_reject(rejects: list[dict[str, str]], line: ParsedLine, reason: str) -> None:
    rejects.append({"source": line.source, "line": line.raw, "reason": reason})


def build_rows(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    actors, actions = load_lookup(root)
    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []

    for line in read_sources(root):
        if line.malformed or line.fields is None:
            add_reject(rejects, line, "malformed_line")
            continue
        fields = {name: line.fields.get(name, "").strip() for name in REQUIRED}
        if any(not fields[name] for name in REQUIRED):
            add_reject(rejects, line, "missing_field")
            continue
        timestamp = parse_ts(fields["timestamp"])
        if timestamp is None:
            add_reject(rejects, line, "invalid_timestamp")
            continue
        actor = actors.get(norm_token(fields["actor"]))
        if actor is None:
            add_reject(rejects, line, "unknown_actor")
            continue
        action = actions.get(norm_token(fields["action"]))
        if action is None:
            add_reject(rejects, line, "unknown_action")
            continue
        event_id = fields["event_id"]
        if event_id in seen:
            add_reject(rejects, line, "duplicate_event")
            continue
        seen.add(event_id)
        normalized.append(
            {
                "timestamp": timestamp,
                "actor_id": actor[0],
                "actor_name": actor[1],
                "action": action,
                "result": fields["result"].lower(),
                "event_id": event_id,
                "source": line.source,
            }
        )
    return normalized, rejects


def write_table(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    root = Path.cwd()
    normalized, rejects = build_rows(root)
    normalized.sort(key=lambda row: (row["timestamp"], row["actor_id"], row["event_id"]))

    out = root / "output"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    write_table(
        out / "normalized.csv",
        ["timestamp", "actor_id", "actor_name", "action", "result", "event_id", "source"],
        normalized,
    )
    write_table(out / "rejects.csv", ["source", "line", "reason"], rejects)
    summary = {
        "actions": dict(sorted(Counter(row["action"] for row in normalized).items())),
        "actors": dict(sorted(Counter(row["actor_id"] for row in normalized).items())),
        "rejected": len(rejects),
        "reject_reasons": dict(sorted(Counter(row["reason"] for row in rejects).items())),
        "rows": len(normalized),
        "sources": dict(sorted(Counter(row["source"] for row in normalized).items())),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

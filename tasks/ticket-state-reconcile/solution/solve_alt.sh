#!/usr/bin/env bash
set -euo pipefail

cat > ticket_sync/sync.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalTicketApi, TransientTicketError


def normalize_key(external_key: str) -> str:
    return external_key.strip().lower()


def _num(ticket: dict[str, Any]) -> int:
    return int(ticket["id"].split("-", 1)[1])


def _emit(rows: list[dict[str, str]], action: str, ticket_id: str, key: str, detail: str) -> None:
    rows.append({"action": action, "ticket_id": ticket_id, "external_key": key, "detail": detail})


def _retry(rows: list[dict[str, str]], ticket_id: str, key: str, detail: str, action):
    try:
        return action()
    except TransientTicketError:
        _emit(rows, "retry", ticket_id, key, detail)
        return action()


def _fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_key": row["external_key"],
        "title": row["title"],
        "owner": row["owner"],
        "severity": row["severity"],
        "labels": list(row["labels"]),
    }


def reconcile_manifest(
    api: LocalTicketApi,
    manifest: list[dict[str, Any]],
    audit_path: str | Path,
) -> None:
    rows: list[dict[str, str]] = []
    for desired in manifest:
        wanted_key = desired["external_key"]
        key = normalize_key(wanted_key)
        tickets = api.list_tickets()
        live = [
            ticket
            for ticket in tickets
            if normalize_key(ticket["external_key"]) == key
            and not ticket.get("archived")
            and ticket.get("status") != "duplicate"
        ]
        live.sort(key=_num)
        if not live:
            created = _retry(
                rows,
                "",
                wanted_key,
                "transient API error",
                lambda: api.create_ticket({**_fields(desired), "status": desired["desired_status"]}),
            )
            _emit(rows, "create", created["id"], wanted_key, "created missing ticket")
            continue

        canonical = live[0]
        duplicate_cleanup = False
        for dupe in live[1:]:
            _retry(
                rows,
                dupe["id"],
                wanted_key,
                "transient API error",
                lambda dupe=dupe: api.mark_duplicate(dupe["id"], canonical["id"]),
            )
            _emit(rows, "dedupe", dupe["id"], wanted_key, f"duplicate of {canonical['id']}")
            duplicate_cleanup = True

        current = next(ticket for ticket in api.list_tickets() if ticket["id"] == canonical["id"])
        fields = _fields(desired)
        field_change = any(current.get(name) != value for name, value in fields.items())
        if field_change:
            current = _retry(
                rows,
                canonical["id"],
                wanted_key,
                "transient API error",
                lambda: api.update_ticket(canonical["id"], fields),
            )
            _emit(rows, "update", canonical["id"], wanted_key, "updated fields")

        status = desired["desired_status"]
        if status == "open" and current["status"] != "open":
            _retry(rows, canonical["id"], wanted_key, "transient API error", lambda: api.reopen_ticket(canonical["id"]))
            _emit(rows, "reopen", canonical["id"], wanted_key, "reopened ticket")
        elif status == "closed" and current["status"] != "closed":
            _retry(rows, canonical["id"], wanted_key, "transient API error", lambda: api.close_ticket(canonical["id"]))
            _emit(rows, "close", canonical["id"], wanted_key, "closed ticket")
        elif not field_change and not duplicate_cleanup:
            _emit(rows, "noop", canonical["id"], wanted_key, "already reconciled")

    Path(audit_path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
PY

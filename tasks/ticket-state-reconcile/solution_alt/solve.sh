#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/ticket_sync/sync.py" <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import json

from .api import LocalTicketApi, TransientTicketError


def normalize_key(external_key: str) -> str:
    return external_key.strip().lower()


def _ticket_number(ticket: dict[str, Any]) -> int:
    return int(str(ticket["id"]).split("-", 1)[1])


def _audit(action: str, ticket_id: str, external_key: str, detail: str) -> dict[str, str]:
    return {
        "action": action,
        "ticket_id": ticket_id,
        "external_key": external_key,
        "detail": detail,
    }


def _with_one_retry(
    audit_rows: list[dict[str, str]],
    ticket_id: str,
    external_key: str,
    detail: str,
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    try:
        return operation()
    except TransientTicketError:
        audit_rows.append(_audit("retry", ticket_id, external_key, detail))
        return operation()


def _desired_fields(desired: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_key": desired["external_key"],
        "title": desired["title"],
        "owner": desired["owner"],
        "severity": desired["severity"],
        "labels": list(desired["labels"]),
    }


def _status_matches(ticket: dict[str, Any], desired: dict[str, Any]) -> bool:
    return ticket.get("status") == desired["desired_status"]


def _fields_match(ticket: dict[str, Any], desired: dict[str, Any]) -> bool:
    return all(ticket.get(key) == value for key, value in _desired_fields(desired).items())


def reconcile_manifest(
    api: LocalTicketApi,
    manifest: list[dict[str, Any]],
    audit_path: str | Path,
) -> None:
    audit_rows: list[dict[str, str]] = []
    for desired in manifest:
        external_key = desired["external_key"]
        matches = [
            ticket
            for ticket in api.list_tickets()
            if not ticket.get("archived")
            and ticket.get("status") != "duplicate"
            and normalize_key(ticket["external_key"]) == normalize_key(external_key)
        ]
        matches.sort(key=_ticket_number)

        if not matches:
            created = _with_one_retry(
                audit_rows,
                "",
                external_key,
                "transient API error",
                lambda: api.create_ticket(
                    {**_desired_fields(desired), "status": desired["desired_status"]}
                ),
            )
            audit_rows.append(_audit("create", created["id"], external_key, "created missing ticket"))
            continue

        canonical = matches[0]
        deduped = False
        for duplicate in matches[1:]:
            _with_one_retry(
                audit_rows,
                duplicate["id"],
                external_key,
                "transient API error",
                lambda duplicate=duplicate: api.mark_duplicate(duplicate["id"], canonical["id"]),
            )
            audit_rows.append(
                _audit("dedupe", duplicate["id"], external_key, f"duplicate of {canonical['id']}")
            )
            deduped = True

        current = next(ticket for ticket in api.list_tickets() if ticket["id"] == canonical["id"])
        fields_changed = not _fields_match(current, desired)
        if fields_changed:
            current = _with_one_retry(
                audit_rows,
                canonical["id"],
                external_key,
                "transient API error",
                lambda: api.update_ticket(canonical["id"], _desired_fields(desired)),
            )
            audit_rows.append(_audit("update", canonical["id"], external_key, "updated fields"))

        if desired["desired_status"] == "open" and not _status_matches(current, desired):
            _with_one_retry(
                audit_rows,
                canonical["id"],
                external_key,
                "transient API error",
                lambda: api.reopen_ticket(canonical["id"]),
            )
            audit_rows.append(_audit("reopen", canonical["id"], external_key, "reopened ticket"))
        elif desired["desired_status"] == "closed" and not _status_matches(current, desired):
            _with_one_retry(
                audit_rows,
                canonical["id"],
                external_key,
                "transient API error",
                lambda: api.close_ticket(canonical["id"]),
            )
            audit_rows.append(_audit("close", canonical["id"], external_key, "closed ticket"))
        elif not fields_changed and not deduped:
            audit_rows.append(_audit("noop", canonical["id"], external_key, "already reconciled"))

    Path(audit_path).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in audit_rows)
    )
PY

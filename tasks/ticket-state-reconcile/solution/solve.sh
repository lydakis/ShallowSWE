#!/usr/bin/env bash
set -euo pipefail

cat > ticket_sync/sync.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import json

from .api import LocalTicketApi, TransientTicketError


def normalize_key(external_key: str) -> str:
    return external_key.strip().lower()


def ticket_number(ticket_id: str) -> int:
    return int(ticket_id.split("-", 1)[1])


def audit(action: str, ticket_id: str, external_key: str, detail: str) -> dict[str, str]:
    return {
        "action": action,
        "ticket_id": ticket_id,
        "external_key": external_key,
        "detail": detail,
    }


def with_retry(
    rows: list[dict[str, str]],
    ticket_id: str,
    external_key: str,
    fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    try:
        return fn()
    except TransientTicketError:
        rows.append(audit("retry", ticket_id, external_key, "transient API error"))
        return fn()


def desired_fields(desired: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_key": desired["external_key"],
        "title": desired["title"],
        "owner": desired["owner"],
        "severity": desired["severity"],
        "labels": list(desired["labels"]),
    }


def matches(ticket: dict[str, Any], desired: dict[str, Any]) -> bool:
    if ticket["external_key"] != desired["external_key"]:
        return False
    if ticket["title"] != desired["title"]:
        return False
    if ticket["owner"] != desired["owner"]:
        return False
    if ticket["severity"] != desired["severity"]:
        return False
    if ticket["labels"] != list(desired["labels"]):
        return False
    return ticket["status"] == desired["desired_status"]


def reconcile_manifest(
    api: LocalTicketApi,
    manifest: list[dict[str, Any]],
    audit_path: str | Path,
) -> None:
    audit_rows: list[dict[str, str]] = []
    for desired in manifest:
        external_key = desired["external_key"]
        key = normalize_key(external_key)
        tickets = api.list_tickets()
        candidates = [
            ticket
            for ticket in tickets
            if not ticket.get("archived")
            and normalize_key(ticket["external_key"]) == key
            and ticket.get("status") != "duplicate"
        ]
        candidates.sort(key=lambda ticket: ticket_number(ticket["id"]))

        if not candidates:
            created = with_retry(
                audit_rows,
                "",
                external_key,
                lambda: api.create_ticket(
                    {
                        **desired_fields(desired),
                        "status": desired["desired_status"],
                    }
                ),
            )
            audit_rows.append(audit("create", created["id"], external_key, "created missing ticket"))
            continue

        canonical = candidates[0]
        had_dedupe = False
        for duplicate in candidates[1:]:
            with_retry(
                audit_rows,
                duplicate["id"],
                external_key,
                lambda duplicate=duplicate: api.mark_duplicate(duplicate["id"], canonical["id"]),
            )
            audit_rows.append(audit("dedupe", duplicate["id"], external_key, f"duplicate of {canonical['id']}"))
            had_dedupe = True

        latest = next(ticket for ticket in api.list_tickets() if ticket["id"] == canonical["id"])
        changed_fields = desired_fields(desired)
        needs_update = any(latest.get(name) != value for name, value in changed_fields.items())
        if needs_update:
            latest = with_retry(
                audit_rows,
                canonical["id"],
                external_key,
                lambda: api.update_ticket(canonical["id"], changed_fields),
            )
            audit_rows.append(audit("update", canonical["id"], external_key, "updated fields"))

        if desired["desired_status"] == "open" and latest["status"] != "open":
            with_retry(audit_rows, canonical["id"], external_key, lambda: api.reopen_ticket(canonical["id"]))
            audit_rows.append(audit("reopen", canonical["id"], external_key, "reopened ticket"))
        elif desired["desired_status"] == "closed" and latest["status"] != "closed":
            with_retry(audit_rows, canonical["id"], external_key, lambda: api.close_ticket(canonical["id"]))
            audit_rows.append(audit("close", canonical["id"], external_key, "closed ticket"))
        elif not needs_update and not had_dedupe:
            audit_rows.append(audit("noop", canonical["id"], external_key, "already reconciled"))

    Path(audit_path).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in audit_rows)
    )
PY

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalTicketApi


def normalize_key(external_key: str) -> str:
    return external_key.strip().lower()


def reconcile_manifest(
    api: LocalTicketApi,
    manifest: list[dict[str, Any]],
    audit_path: str | Path,
) -> None:
    audit_rows: list[dict[str, str]] = []
    tickets = api.list_tickets()
    for desired in manifest:
        external_key = desired["external_key"]
        match = next(
            (
                ticket
                for ticket in tickets
                if not ticket.get("archived")
                and normalize_key(ticket["external_key"]) == normalize_key(external_key)
            ),
            None,
        )
        fields = {
            "external_key": external_key,
            "title": desired["title"],
            "owner": desired["owner"],
            "severity": desired["severity"],
            "labels": list(desired["labels"]),
            "status": desired["desired_status"],
        }
        if match is None:
            created = api.create_ticket(fields)
            audit_rows.append(
                {
                    "action": "create",
                    "ticket_id": created["id"],
                    "external_key": external_key,
                    "detail": "created missing ticket",
                }
            )
        else:
            updated = api.update_ticket(match["id"], fields)
            audit_rows.append(
                {
                    "action": "update",
                    "ticket_id": updated["id"],
                    "external_key": external_key,
                    "detail": "updated existing ticket",
                }
            )
        tickets = api.list_tickets()

    Path(audit_path).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in audit_rows)
    )

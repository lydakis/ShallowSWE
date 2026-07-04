from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json


class TransientTicketError(RuntimeError):
    pass


class LocalTicketApi:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = copy.deepcopy(state)
        self.state.setdefault("tickets", [])
        self.state.setdefault("call_log", [])
        self.state.setdefault("transient_fail_once", [])
        self._failed_once: set[str] = set()

    @classmethod
    def load(cls, path: str | Path) -> "LocalTicketApi":
        return cls(json.loads(Path(path).read_text()))

    def dump(self, path: str | Path) -> None:
        tickets = sorted(self.state["tickets"], key=lambda ticket: _ticket_number(ticket["id"]))
        output = dict(self.state)
        output["tickets"] = tickets
        Path(path).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")

    def list_tickets(self) -> list[dict[str, Any]]:
        self._log("list", None, {})
        return copy.deepcopy(self.state["tickets"])

    def create_ticket(self, fields: dict[str, Any]) -> dict[str, Any]:
        key = f"create:{fields['external_key']}"
        self._maybe_transient(key)
        ticket = {
            "id": self.next_ticket_id(),
            "external_key": fields["external_key"],
            "title": fields["title"],
            "owner": fields["owner"],
            "severity": fields["severity"],
            "status": fields["status"],
            "labels": list(fields["labels"]),
            "archived": False,
        }
        self.state["tickets"].append(ticket)
        self._log("create", ticket["id"], {"external_key": ticket["external_key"]})
        return copy.deepcopy(ticket)

    def update_ticket(self, ticket_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        ticket = self._get_ticket(ticket_id)
        key = f"update:{ticket['external_key']}"
        self._maybe_transient(key)
        ticket.update(copy.deepcopy(fields))
        self._log("update", ticket_id, {"fields": sorted(fields)})
        return copy.deepcopy(ticket)

    def close_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = self._get_ticket(ticket_id)
        key = f"close:{ticket['external_key']}"
        self._maybe_transient(key)
        ticket["status"] = "closed"
        self._log("close", ticket_id, {})
        return copy.deepcopy(ticket)

    def reopen_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = self._get_ticket(ticket_id)
        key = f"reopen:{ticket['external_key']}"
        self._maybe_transient(key)
        ticket["status"] = "open"
        self._log("reopen", ticket_id, {})
        return copy.deepcopy(ticket)

    def mark_duplicate(self, ticket_id: str, duplicate_of: str) -> dict[str, Any]:
        ticket = self._get_ticket(ticket_id)
        key = f"duplicate:{ticket['external_key']}"
        self._maybe_transient(key)
        ticket["status"] = "duplicate"
        ticket["duplicate_of"] = duplicate_of
        self._log("duplicate", ticket_id, {"duplicate_of": duplicate_of})
        return copy.deepcopy(ticket)

    def next_ticket_id(self) -> str:
        largest = max((_ticket_number(ticket["id"]) for ticket in self.state["tickets"]), default=0)
        return f"TKT-{largest + 1}"

    def _get_ticket(self, ticket_id: str) -> dict[str, Any]:
        for ticket in self.state["tickets"]:
            if ticket["id"] == ticket_id:
                return ticket
        raise KeyError(ticket_id)

    def _maybe_transient(self, key: str) -> None:
        if key in self.state["transient_fail_once"] and key not in self._failed_once:
            self._failed_once.add(key)
            self._log("transient", None, {"key": key})
            raise TransientTicketError(key)

    def _log(self, action: str, ticket_id: str | None, detail: dict[str, Any]) -> None:
        self.state["call_log"].append(
            {"action": action, "ticket_id": ticket_id, "detail": detail}
        )


def _ticket_number(ticket_id: str) -> int:
    return int(ticket_id.split("-", 1)[1])

from __future__ import annotations


class StatusError(ValueError):
    pass


OPEN_STATUSES = {
    "new",
    "packed",
    "shipped",
    "out_for_delivery",
    "hold",
    "pending_review",
}
TERMINAL_STATUSES = {"delivered", "cancelled", "lost"}
SUCCESSFUL_STATUSES = {"delivered"}
STATUS_ALIASES = {
    "canceled": "cancelled",
    "lost_in_transit": "lost",
}


def known_statuses() -> set[str]:
    return set(OPEN_STATUSES | TERMINAL_STATUSES)


def normalize_status(raw_status: str) -> str:
    status = raw_status.strip().lower()
    status = STATUS_ALIASES.get(status, status)
    if status not in known_statuses():
        raise StatusError(f"unknown status: {raw_status}")
    return status


def is_terminal_status(raw_status: str) -> bool:
    return normalize_status(raw_status) in TERMINAL_STATUSES


def is_successful_status(raw_status: str) -> bool:
    return normalize_status(raw_status) in SUCCESSFUL_STATUSES


def status_help() -> str:
    statuses = sorted(known_statuses())
    aliases = sorted(STATUS_ALIASES)
    return "known statuses: " + ", ".join(statuses + aliases)

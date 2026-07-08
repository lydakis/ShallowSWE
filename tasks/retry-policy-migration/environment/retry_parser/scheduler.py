from __future__ import annotations

from retry_parser.parser import parse_retry_row


LEGACY_KEYS = ("job_id", "attempts", "delay_seconds", "mode")


def build_retry_plan(row: dict[str, str]) -> dict[str, object]:
    parsed = parse_retry_row(row)
    return {key: parsed[key] for key in LEGACY_KEYS}

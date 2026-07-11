from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def raw_usage_totals_from_trajectory(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        trajectory = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None

    usage_entries: list[dict[str, Any]] = []
    _collect_usage_entries(trajectory, usage_entries)
    if not usage_entries:
        return None
    return {
        "input_tokens": sum(_usage_input_tokens(usage) for usage in usage_entries),
        "output_tokens": sum(_usage_output_tokens(usage) for usage in usage_entries),
        "cache_read_tokens": sum(
            _usage_cache_read_tokens(usage) for usage in usage_entries
        ),
        "cache_write_tokens": sum(
            _usage_cache_write_tokens(usage) for usage in usage_entries
        ),
        "reasoning_tokens": sum(
            _usage_reasoning_tokens(usage) for usage in usage_entries
        ),
        "gateway_reported_cost_usd": _sum_optional_float(
            usage.get("cost") for usage in usage_entries
        ),
    }


def _collect_usage_entries(value: Any, entries: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        usage = value.get("usage")
        if isinstance(usage, dict):
            entries.append(usage)
        for child in value.values():
            _collect_usage_entries(child, entries)
    elif isinstance(value, list):
        for child in value:
            _collect_usage_entries(child, entries)


def _usage_input_tokens(usage: dict[str, Any]) -> int:
    return _first_int(usage, ("input_tokens", "prompt_tokens"))


def _usage_output_tokens(usage: dict[str, Any]) -> int:
    return _first_int(usage, ("output_tokens", "completion_tokens"))


def _usage_cache_read_tokens(usage: dict[str, Any]) -> int:
    details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
    if not isinstance(details, dict):
        return 0
    return _int_or_zero(details.get("cached_tokens"))


def _usage_cache_write_tokens(usage: dict[str, Any]) -> int:
    details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
    if not isinstance(details, dict):
        return _first_int(
            usage,
            ("cache_creation_input_tokens", "cache_write_input_tokens"),
        )
    for key in ("cache_creation_tokens", "cache_write_tokens"):
        if details.get(key) is not None:
            return _int_or_zero(details.get(key))
    return _first_int(
        usage,
        ("cache_creation_input_tokens", "cache_write_input_tokens"),
    )


def _usage_reasoning_tokens(usage: dict[str, Any]) -> int:
    details = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
    if not isinstance(details, dict):
        return 0
    return _int_or_zero(details.get("reasoning_tokens"))


def _first_int(mapping: dict[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in mapping:
            return _int_or_zero(mapping[key])
    return 0


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sum_optional_float(values: Any) -> float | None:
    total = 0.0
    seen = False
    for value in values:
        if value is None:
            continue
        try:
            total += float(value)
            seen = True
        except (TypeError, ValueError):
            continue
    return total if seen else None

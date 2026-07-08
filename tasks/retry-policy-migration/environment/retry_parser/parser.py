from __future__ import annotations


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def parse_retry_row(row: dict[str, str]) -> dict[str, object]:
    try:
        attempts = int(row["attempts"])
        delay_seconds = int(row["delay_seconds"])
        max_attempts = int(row.get("max_attempts", row["attempts"]))
    except (KeyError, TypeError, ValueError):
        return {
            "job_id": row.get("job_id", ""),
            "attempts": 0,
            "delay_seconds": 30,
            "mode": "fallback",
        }

    return {
        "job_id": row["job_id"],
        "attempts": attempts,
        "delay_seconds": delay_seconds,
        "max_attempts": max_attempts,
        "retryable": parse_bool(row.get("retryable", "")),
        "status": row.get("status", ""),
        "mode": row.get("mode") or "standard",
    }

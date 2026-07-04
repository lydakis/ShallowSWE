#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

Path("/app/ledger_migrator/migrate.py").write_text(
    r'''from __future__ import annotations

from pathlib import Path
import csv
import json


NORMALIZED_FIELDS = ["event_id", "account_id", "plan_id", "units", "currency", "gross_cents", "source", "occurred_at"]
LEDGER_FIELDS = ["account_id", "event_id", "event_type", "amount_cents", "running_balance_cents"]
REJECT_FIELDS = ["input", "event_id", "reason"]


def migrate(input_dir: str | Path, output_dir: str | Path) -> None:
    root = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    account_rows = {row["account_id"]: row for row in _csv_rows(root / "accounts.csv")}
    plan_rows = {row["plan_id"]: row for row in json.loads((root / "plans.json").read_text())}
    rejects: list[dict[str, str]] = []

    valid_usage = []
    accepted_usage_ids: set[str] = set()
    for raw in _jsonl_rows(root / "usage.jsonl"):
        event_id = str(raw.get("usage_id", ""))
        account = account_rows.get(str(raw.get("account_id", "")))
        reason = _usage_reject_reason(raw, account, plan_rows, accepted_usage_ids)
        if reason is not None:
            rejects.append({"input": "usage", "event_id": event_id, "reason": reason})
            continue
        account_id = str(raw["account_id"])
        plan_id = str(raw.get("plan_id") or account["plan_id"])
        units = int(raw["units"])
        plan = plan_rows[plan_id]
        accepted_usage_ids.add(event_id)
        valid_usage.append(
            {
                "event_id": event_id,
                "account_id": account_id,
                "plan_id": plan_id,
                "units": units,
                "currency": str(plan["currency"]),
                "gross_cents": units * int(plan["unit_price_cents"]),
                "source": str(raw.get("source") or "legacy"),
                "occurred_at": str(raw["occurred_at"]),
            }
        )

    valid_usage.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
    adjustments = _money_events(root / "legacy_adjustments.csv", "adjustment_id", "adjustment", account_rows, rejects)
    credits = _money_events(root / "credits.csv", "credit_id", "credit", account_rows, rejects)
    ledger = _ledger(valid_usage, adjustments, credits)
    rejects.sort(key=lambda row: (row["input"], row["event_id"]))

    _write_jsonl(out / "normalized_events.jsonl", valid_usage)
    _write_csv(out / "ledger.csv", LEDGER_FIELDS, ledger)
    _write_csv(out / "rejects.csv", REJECT_FIELDS, rejects)
    usage_total = sum(row["gross_cents"] for row in valid_usage)
    adjustment_total = sum(row["amount_cents"] for row in ledger if row["event_type"] == "adjustment")
    credit_total = sum(row["amount_cents"] for row in ledger if row["event_type"] == "credit")
    (out / "summary.json").write_text(
        json.dumps(
            {
                "usage_events": len(valid_usage),
                "adjustment_events": len([row for row in ledger if row["event_type"] == "adjustment"]),
                "credit_events": len([row for row in ledger if row["event_type"] == "credit"]),
                "reject_count": len(rejects),
                "gross_cents": usage_total,
                "adjustment_cents": adjustment_total,
                "credit_cents": credit_total,
                "net_cents": usage_total + adjustment_total + credit_total,
            },
            sort_keys=True,
        )
        + "\n"
    )


def _usage_reject_reason(raw: dict[str, object], account: dict[str, str] | None, plans: dict[str, dict[str, object]], seen: set[str]) -> str | None:
    if account is None:
        return "UNKNOWN_ACCOUNT"
    if account["status"] != "active":
        return "SUSPENDED_ACCOUNT"
    plan_id = str(raw.get("plan_id") or account["plan_id"])
    if plan_id not in plans:
        return "UNKNOWN_PLAN"
    if not _is_positive_int(raw.get("units")):
        return "INVALID_UNITS"
    if str(raw.get("usage_id", "")) in seen:
        return "DUPLICATE_USAGE_ID"
    return None


def _money_events(path: Path, id_field: str, input_name: str, accounts: dict[str, dict[str, str]], rejects: list[dict[str, str]]) -> list[dict[str, object]]:
    rows = []
    for raw in _csv_rows(path):
        event_id = raw[id_field]
        account = accounts.get(raw["account_id"])
        if account is None:
            rejects.append({"input": input_name, "event_id": event_id, "reason": "UNKNOWN_ACCOUNT"})
            continue
        if account["status"] != "active":
            rejects.append({"input": input_name, "event_id": event_id, "reason": "SUSPENDED_ACCOUNT"})
            continue
        rows.append({"account_id": raw["account_id"], "event_id": event_id, "amount_cents": int(raw["amount_cents"])})
    return sorted(rows, key=lambda row: row["event_id"])


def _ledger(usage: list[dict[str, object]], adjustments: list[dict[str, object]], credits: list[dict[str, object]]) -> list[dict[str, object]]:
    accounts = sorted({*(row["account_id"] for row in usage), *(row["account_id"] for row in adjustments), *(row["account_id"] for row in credits)})
    result = []
    for account_id in accounts:
        balance = 0
        account_usage = [row for row in usage if row["account_id"] == account_id]
        account_usage.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
        for row in account_usage:
            balance += int(row["gross_cents"])
            result.append(_row(account_id, row["event_id"], "usage", row["gross_cents"], balance))
        for row in [item for item in adjustments if item["account_id"] == account_id]:
            amount = int(row["amount_cents"])
            balance += amount
            result.append(_row(account_id, row["event_id"], "adjustment", amount, balance))
        for row in [item for item in credits if item["account_id"] == account_id]:
            amount = -min(max(0, int(row["amount_cents"])), max(0, balance))
            balance += amount
            result.append(_row(account_id, row["event_id"], "credit", amount, balance))
    return result


def _row(account_id: str, event_id: object, event_type: str, amount: object, balance: int) -> dict[str, object]:
    return {
        "account_id": account_id,
        "event_id": str(event_id),
        "event_type": event_type,
        "amount_cents": int(amount),
        "running_balance_cents": balance,
    }


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _jsonl_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _is_positive_int(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        text = str(value)
        parsed = int(text)
    except (TypeError, ValueError):
        return False
    return parsed > 0 and text.strip() == str(parsed)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps({field: row[field] for field in NORMALIZED_FIELDS}, sort_keys=True) + "\n")
'''
)
PY

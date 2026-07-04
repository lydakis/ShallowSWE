#!/usr/bin/env bash
set -euo pipefail

cat > /app/ledger_migrator/migrate.py <<'PY'
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv
import json


NORMALIZED_FIELDS = [
    "event_id",
    "account_id",
    "plan_id",
    "units",
    "currency",
    "gross_cents",
    "source",
    "occurred_at",
]
LEDGER_FIELDS = [
    "account_id",
    "event_id",
    "event_type",
    "amount_cents",
    "running_balance_cents",
]
REJECT_FIELDS = ["input", "event_id", "reason"]


def migrate(input_dir: str | Path, output_dir: str | Path) -> None:
    source = Path(input_dir)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    accounts = _read_accounts(source / "accounts.csv")
    plans = _read_plans(source / "plans.json")
    rejects: list[dict[str, str]] = []
    normalized = _valid_usage_events(source / "usage.jsonl", accounts, plans, rejects)
    adjustments = _valid_money_rows(
        source / "legacy_adjustments.csv",
        "adjustment_id",
        "adjustment",
        accounts,
        rejects,
    )
    credits = _valid_money_rows(
        source / "credits.csv",
        "credit_id",
        "credit",
        accounts,
        rejects,
    )

    ledger_rows = _build_ledger(normalized, adjustments, credits)
    rejects.sort(key=lambda row: (row["input"], row["event_id"]))

    _write_jsonl(target / "normalized_events.jsonl", normalized, NORMALIZED_FIELDS)
    _write_csv(target / "ledger.csv", LEDGER_FIELDS, ledger_rows)
    _write_csv(target / "rejects.csv", REJECT_FIELDS, rejects)
    _write_summary(target / "summary.json", normalized, ledger_rows, rejects)


def _valid_usage_events(
    path: Path,
    accounts: dict[str, dict[str, str]],
    plans: dict[str, dict[str, object]],
    rejects: list[dict[str, str]],
) -> list[dict[str, object]]:
    seen_valid: set[str] = set()
    events: list[dict[str, object]] = []
    for row in _read_jsonl(path):
        usage_id = str(row.get("usage_id") or "")
        account_id = str(row.get("account_id") or "")
        account = accounts.get(account_id)
        if account is None:
            rejects.append(_reject("usage", usage_id, "UNKNOWN_ACCOUNT"))
            continue
        if account.get("status") != "active":
            rejects.append(_reject("usage", usage_id, "SUSPENDED_ACCOUNT"))
            continue
        plan_id = str(row.get("plan_id") or account.get("plan_id") or "")
        plan = plans.get(plan_id)
        if plan is None:
            rejects.append(_reject("usage", usage_id, "UNKNOWN_PLAN"))
            continue
        units = _positive_int(row.get("units"))
        if units is None:
            rejects.append(_reject("usage", usage_id, "INVALID_UNITS"))
            continue
        if usage_id in seen_valid:
            rejects.append(_reject("usage", usage_id, "DUPLICATE_USAGE_ID"))
            continue
        seen_valid.add(usage_id)
        events.append(
            {
                "event_id": usage_id,
                "account_id": account_id,
                "plan_id": plan_id,
                "units": units,
                "currency": str(plan["currency"]),
                "gross_cents": units * int(plan["unit_price_cents"]),
                "source": str(row.get("source") or "legacy"),
                "occurred_at": str(row["occurred_at"]),
            }
        )
    events.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
    return events


def _valid_money_rows(
    path: Path,
    id_field: str,
    input_name: str,
    accounts: dict[str, dict[str, str]],
    rejects: list[dict[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in _read_optional_csv(path):
        event_id = row[id_field]
        account = accounts.get(row["account_id"])
        if account is None:
            rejects.append(_reject(input_name, event_id, "UNKNOWN_ACCOUNT"))
            continue
        if account.get("status") != "active":
            rejects.append(_reject(input_name, event_id, "SUSPENDED_ACCOUNT"))
            continue
        rows.append(
            {
                "account_id": row["account_id"],
                "event_id": event_id,
                "amount_cents": int(row["amount_cents"]),
            }
        )
    rows.sort(key=lambda row: row["event_id"])
    return rows


def _build_ledger(
    normalized: list[dict[str, object]],
    adjustments: list[dict[str, object]],
    credits: list[dict[str, object]],
) -> list[dict[str, object]]:
    usage_by_account: dict[str, list[dict[str, object]]] = defaultdict(list)
    adjustment_by_account: dict[str, list[dict[str, object]]] = defaultdict(list)
    credit_by_account: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in normalized:
        usage_by_account[str(row["account_id"])].append(row)
    for row in adjustments:
        adjustment_by_account[str(row["account_id"])].append(row)
    for row in credits:
        credit_by_account[str(row["account_id"])].append(row)

    ledger: list[dict[str, object]] = []
    for account_id in sorted(
        set(usage_by_account) | set(adjustment_by_account) | set(credit_by_account)
    ):
        balance = 0
        for event in usage_by_account[account_id]:
            balance += int(event["gross_cents"])
            ledger.append(_ledger_row(account_id, str(event["event_id"]), "usage", int(event["gross_cents"]), balance))
        for event in adjustment_by_account[account_id]:
            amount = int(event["amount_cents"])
            balance += amount
            ledger.append(_ledger_row(account_id, str(event["event_id"]), "adjustment", amount, balance))
        for event in credit_by_account[account_id]:
            requested = max(0, int(event["amount_cents"]))
            amount = -min(requested, max(0, balance))
            balance += amount
            ledger.append(_ledger_row(account_id, str(event["event_id"]), "credit", amount, balance))
    return ledger


def _ledger_row(
    account_id: str,
    event_id: str,
    event_type: str,
    amount_cents: int,
    running_balance_cents: int,
) -> dict[str, object]:
    return {
        "account_id": account_id,
        "event_id": event_id,
        "event_type": event_type,
        "amount_cents": amount_cents,
        "running_balance_cents": running_balance_cents,
    }


def _write_summary(
    path: Path,
    normalized: list[dict[str, object]],
    ledger_rows: list[dict[str, object]],
    rejects: list[dict[str, str]],
) -> None:
    gross = sum(int(row["gross_cents"]) for row in normalized)
    adjustment = sum(int(row["amount_cents"]) for row in ledger_rows if row["event_type"] == "adjustment")
    credit = sum(int(row["amount_cents"]) for row in ledger_rows if row["event_type"] == "credit")
    summary = {
        "usage_events": len(normalized),
        "adjustment_events": sum(1 for row in ledger_rows if row["event_type"] == "adjustment"),
        "credit_events": sum(1 for row in ledger_rows if row["event_type"] == "credit"),
        "reject_count": len(rejects),
        "gross_cents": gross,
        "adjustment_cents": adjustment,
        "credit_cents": credit,
        "net_cents": gross + adjustment + credit,
    }
    path.write_text(json.dumps(summary, sort_keys=True) + "\n")


def _read_accounts(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="") as handle:
        return {row["account_id"]: row for row in csv.DictReader(handle)}


def _read_plans(path: Path) -> dict[str, dict[str, object]]:
    return {row["plan_id"]: row for row in json.loads(path.read_text())}


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _read_optional_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(str(value))
    except (TypeError, ValueError):
        return None
    return result if result > 0 and str(value).strip() == str(result) else None


def _reject(input_name: str, event_id: str, reason: str) -> dict[str, str]:
    return {"input": input_name, "event_id": event_id, "reason": reason}


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps({field: row[field] for field in fields}, sort_keys=True) + "\n")
PY

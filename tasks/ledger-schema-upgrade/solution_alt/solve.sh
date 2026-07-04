#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/ledger_migrator/migrate.py" <<'PY'
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

    usage = _accepted_usage(source / "usage.jsonl", accounts, plans, rejects)
    adjustments = _accepted_amounts(
        source / "legacy_adjustments.csv",
        "adjustment_id",
        "adjustment",
        accounts,
        rejects,
    )
    credits = _accepted_amounts(
        source / "credits.csv",
        "credit_id",
        "credit",
        accounts,
        rejects,
    )
    ledger = _ledger_rows(usage, adjustments, credits)
    rejects.sort(key=lambda row: (row["input"], row["event_id"]))

    _write_jsonl(target / "normalized_events.jsonl", usage)
    _write_csv(target / "ledger.csv", LEDGER_FIELDS, ledger)
    _write_csv(target / "rejects.csv", REJECT_FIELDS, rejects)
    _write_summary(target / "summary.json", usage, ledger, rejects)


def _accepted_usage(
    path: Path,
    accounts: dict[str, dict[str, str]],
    plans: dict[str, dict[str, object]],
    rejects: list[dict[str, str]],
) -> list[dict[str, object]]:
    accepted: list[dict[str, object]] = []
    valid_ids: set[str] = set()

    for raw in _read_jsonl(path):
        event_id = str(raw.get("usage_id") or "")
        account_id = str(raw.get("account_id") or "")
        account = accounts.get(account_id)
        if account is None:
            rejects.append(_reject("usage", event_id, "UNKNOWN_ACCOUNT"))
            continue
        if account["status"] != "active":
            rejects.append(_reject("usage", event_id, "SUSPENDED_ACCOUNT"))
            continue

        plan_id = str(raw.get("plan_id") or account["plan_id"])
        plan = plans.get(plan_id)
        if plan is None:
            rejects.append(_reject("usage", event_id, "UNKNOWN_PLAN"))
            continue

        units = _strict_positive_int(raw.get("units"))
        if units is None:
            rejects.append(_reject("usage", event_id, "INVALID_UNITS"))
            continue
        if event_id in valid_ids:
            rejects.append(_reject("usage", event_id, "DUPLICATE_USAGE_ID"))
            continue
        valid_ids.add(event_id)

        accepted.append(
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

    accepted.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
    return accepted


def _accepted_amounts(
    path: Path,
    id_field: str,
    input_name: str,
    accounts: dict[str, dict[str, str]],
    rejects: list[dict[str, str]],
) -> list[dict[str, object]]:
    accepted: list[dict[str, object]] = []
    for row in _read_optional_csv(path):
        event_id = row[id_field]
        account = accounts.get(row["account_id"])
        if account is None:
            rejects.append(_reject(input_name, event_id, "UNKNOWN_ACCOUNT"))
            continue
        if account["status"] != "active":
            rejects.append(_reject(input_name, event_id, "SUSPENDED_ACCOUNT"))
            continue
        accepted.append(
            {
                "account_id": row["account_id"],
                "event_id": event_id,
                "amount_cents": int(row["amount_cents"]),
            }
        )
    accepted.sort(key=lambda row: str(row["event_id"]))
    return accepted


def _ledger_rows(
    usage: list[dict[str, object]],
    adjustments: list[dict[str, object]],
    credits: list[dict[str, object]],
) -> list[dict[str, object]]:
    usage_by_account = _group_by_account(usage)
    adjustment_by_account = _group_by_account(adjustments)
    credit_by_account = _group_by_account(credits)
    accounts = sorted(set(usage_by_account) | set(adjustment_by_account) | set(credit_by_account))

    rows: list[dict[str, object]] = []
    for account_id in accounts:
        balance = 0
        for event in usage_by_account[account_id]:
            amount = int(event["gross_cents"])
            balance += amount
            rows.append(_ledger_row(account_id, str(event["event_id"]), "usage", amount, balance))
        for event in adjustment_by_account[account_id]:
            amount = int(event["amount_cents"])
            balance += amount
            rows.append(_ledger_row(account_id, str(event["event_id"]), "adjustment", amount, balance))
        for event in credit_by_account[account_id]:
            amount = -min(max(int(event["amount_cents"]), 0), max(balance, 0))
            balance += amount
            rows.append(_ledger_row(account_id, str(event["event_id"]), "credit", amount, balance))
    return rows


def _group_by_account(rows: list[dict[str, object]]) -> defaultdict[str, list[dict[str, object]]]:
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["account_id"])].append(row)
    return grouped


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
    usage: list[dict[str, object]],
    ledger: list[dict[str, object]],
    rejects: list[dict[str, str]],
) -> None:
    usage_total = sum(int(row["gross_cents"]) for row in usage)
    adjustment_total = sum(int(row["amount_cents"]) for row in ledger if row["event_type"] == "adjustment")
    credit_total = sum(int(row["amount_cents"]) for row in ledger if row["event_type"] == "credit")
    summary = {
        "usage_events": len(usage),
        "adjustment_events": sum(1 for row in ledger if row["event_type"] == "adjustment"),
        "credit_events": sum(1 for row in ledger if row["event_type"] == "credit"),
        "reject_count": len(rejects),
        "gross_cents": usage_total,
        "adjustment_cents": adjustment_total,
        "credit_cents": credit_total,
        "net_cents": usage_total + adjustment_total + credit_total,
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


def _strict_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text.isdecimal():
        return None
    parsed = int(text)
    return parsed if parsed > 0 else None


def _reject(input_name: str, event_id: str, reason: str) -> dict[str, str]:
    return {"input": input_name, "event_id": event_id, "reason": reason}


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps({field: row[field] for field in NORMALIZED_FIELDS}, sort_keys=True) + "\n")
PY

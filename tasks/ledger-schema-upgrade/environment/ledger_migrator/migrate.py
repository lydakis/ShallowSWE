from __future__ import annotations

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
    usage_rows = _read_usage(source / "usage.jsonl")

    normalized: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    rejects: list[dict[str, str]] = []

    for row in usage_rows:
        account_id = str(row.get("account_id") or "")
        account = accounts.get(account_id)
        if account is None:
            rejects.append(_reject("usage", str(row.get("usage_id") or ""), "UNKNOWN_ACCOUNT"))
            continue
        plan_id = str(row.get("plan_id") or account["plan_id"])
        plan = plans.get(plan_id)
        if plan is None:
            rejects.append(_reject("usage", str(row.get("usage_id") or ""), "UNKNOWN_PLAN"))
            continue
        units = int(row.get("units", 0))
        event = {
            "event_id": str(row["usage_id"]),
            "account_id": account_id,
            "plan_id": plan_id,
            "units": units,
            "currency": plan["currency"],
            "gross_cents": units * int(plan["unit_price_cents"]),
            "source": str(row.get("source") or "legacy"),
            "occurred_at": str(row["occurred_at"]),
        }
        normalized.append(event)

    normalized.sort(key=lambda item: (item["occurred_at"], item["event_id"]))
    balances: dict[str, int] = {}
    for event in normalized:
        account_id = str(event["account_id"])
        balances[account_id] = balances.get(account_id, 0) + int(event["gross_cents"])
        ledger_rows.append(
            {
                "account_id": account_id,
                "event_id": event["event_id"],
                "event_type": "usage",
                "amount_cents": event["gross_cents"],
                "running_balance_cents": balances[account_id],
            }
        )

    _write_jsonl(target / "normalized_events.jsonl", normalized, NORMALIZED_FIELDS)
    _write_csv(target / "ledger.csv", LEDGER_FIELDS, ledger_rows)
    _write_csv(target / "rejects.csv", REJECT_FIELDS, rejects)
    (target / "summary.json").write_text(
        json.dumps(
            {
                "usage_events": len(normalized),
                "adjustment_events": 0,
                "credit_events": 0,
                "reject_count": len(rejects),
                "gross_cents": sum(int(row["gross_cents"]) for row in normalized),
                "adjustment_cents": 0,
                "credit_cents": 0,
                "net_cents": sum(int(row["gross_cents"]) for row in normalized),
            },
            sort_keys=True,
        )
        + "\n"
    )


def _read_accounts(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="") as handle:
        return {row["account_id"]: row for row in csv.DictReader(handle)}


def _read_plans(path: Path) -> dict[str, dict[str, object]]:
    return {row["plan_id"]: row for row in json.loads(path.read_text())}


def _read_usage(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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

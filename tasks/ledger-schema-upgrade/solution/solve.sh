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
    "discount_cents",
    "tax_cents",
    "net_cents",
    "usd_net_micros",
    "source",
    "occurred_at",
    "recognition_month",
]
LEDGER_FIELDS = [
    "account_id",
    "currency",
    "event_id",
    "event_type",
    "amount_cents",
    "amount_usd_micros",
    "running_balance_cents",
    "running_balance_usd_micros",
    "recognition_month",
]
BALANCE_FIELDS = [
    "account_id",
    "region",
    "segment",
    "currency",
    "ending_balance_cents",
    "ending_balance_usd_micros",
    "status",
]
PLAN_FIELDS = [
    "recognition_month",
    "plan_id",
    "currency",
    "gross_cents",
    "discount_cents",
    "tax_cents",
    "net_cents",
    "net_usd_micros",
]
REJECT_FIELDS = ["input", "event_id", "reason"]


def migrate(input_dir: str | Path, output_dir: str | Path) -> None:
    source = Path(input_dir)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    context = Context(source)
    rejects: list[dict[str, str]] = []
    usage = context.accepted_usage(rejects)
    adjustments = context.accepted_amounts(
        source / "legacy_adjustments.csv",
        "adjustment_id",
        "adjustment",
        "effective_at",
        rejects,
    )
    credits = context.accepted_amounts(
        source / "credits.csv",
        "credit_id",
        "credit",
        "issued_at",
        rejects,
    )
    ledger = context.ledger_rows(usage, adjustments, credits)
    balances = context.balance_rows(ledger)
    revenue = context.plan_revenue_rows(usage)
    rejects.sort(key=lambda row: (row["input"], row["event_id"]))

    _write_jsonl(target / "normalized_events.jsonl", usage, NORMALIZED_FIELDS)
    _write_csv(target / "ledger.csv", LEDGER_FIELDS, ledger)
    _write_csv(target / "account_balances.csv", BALANCE_FIELDS, balances)
    _write_csv(target / "plan_revenue.csv", PLAN_FIELDS, revenue)
    _write_csv(target / "rejects.csv", REJECT_FIELDS, rejects)
    audit = {
        "schema_version": "v4",
        "source_files": sorted(path.name for path in source.iterdir() if path.is_file()),
        "normalized_events": len(usage),
        "ledger_rows": len(ledger),
        "account_balance_rows": len(balances),
        "plan_revenue_rows": len(revenue),
        "reject_count": len(rejects),
        "currencies": sorted({row["currency"] for row in ledger}),
        "net_usd_micros": sum(int(row["amount_usd_micros"]) for row in ledger),
        "generated_at": "deterministic",
    }
    (target / "migration_audit.json").write_text(json.dumps(audit, sort_keys=True) + "\n")
    _write_compat_summary(target / "summary.json", usage, ledger, rejects)


class Context:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.accounts = {row["account_id"]: row for row in _read_csv(source / "accounts.csv")}
        self.plans = {row["plan_id"]: row for row in json.loads((source / "plans.json").read_text())}
        self.rates = {"USD": 1000000}
        for row in _read_optional_csv(source / "exchange_rates.csv"):
            self.rates[row["currency"]] = int(row["to_usd_rate_micros"])
        self.discounts = {
            row["discount_code"]: row for row in _read_optional_csv(source / "discounts.csv")
        }
        self.overrides = _read_optional_csv(source / "account_overrides.csv")

    def effective_account(self, account_id: str, timestamp: str) -> tuple[dict[str, str] | None, str, str]:
        account = self.accounts.get(account_id)
        if account is None:
            return None, "", ""
        status = account.get("status", "")
        plan_id = account.get("plan_id", "")
        for row in sorted(self.overrides, key=lambda item: item["effective_at"]):
            if row["account_id"] == account_id and row["effective_at"] <= timestamp:
                status = row.get("status_override") or status
                plan_id = row.get("plan_override_id") or plan_id
        return account, status, plan_id

    def final_status(self, account_id: str) -> str:
        status = self.accounts[account_id]["status"]
        for row in sorted(self.overrides, key=lambda item: item["effective_at"]):
            if row["account_id"] == account_id and row.get("status_override"):
                status = row["status_override"]
        return status

    def usd_micros(self, amount_cents: int, currency: str) -> int:
        return _round_half_up(amount_cents * self.rates[currency])

    def reject(self, rejects: list[dict[str, str]], input_name: str, event_id: str, reason: str) -> None:
        rejects.append({"input": input_name, "event_id": event_id, "reason": reason})

    def accepted_usage(self, rejects: list[dict[str, str]]) -> list[dict[str, object]]:
        accepted: list[dict[str, object]] = []
        seen_usage: set[str] = set()
        seen_idempotency: set[str] = set()
        for raw in _read_jsonl(self.source / "usage.jsonl"):
            event_id = str(raw.get("usage_id") or "")
            timestamp = str(raw.get("occurred_at") or "")
            account_id = str(raw.get("account_id") or "")
            account, status, account_plan = self.effective_account(account_id, timestamp)
            if account is None:
                self.reject(rejects, "usage", event_id, "UNKNOWN_ACCOUNT")
                continue
            if status != "active":
                self.reject(rejects, "usage", event_id, "SUSPENDED_ACCOUNT")
                continue
            plan_id = str(raw.get("plan_id") or account_plan)
            plan = self.plans.get(plan_id)
            if plan is None:
                self.reject(rejects, "usage", event_id, "UNKNOWN_PLAN")
                continue
            currency = str(plan["currency"])
            if currency not in self.rates:
                self.reject(rejects, "usage", event_id, "UNKNOWN_CURRENCY")
                continue
            units = _positive_int(raw.get("quantity", raw.get("units")))
            if units is None:
                self.reject(rejects, "usage", event_id, "INVALID_UNITS")
                continue
            if event_id in seen_usage:
                self.reject(rejects, "usage", event_id, "DUPLICATE_USAGE_ID")
                continue
            key = str(raw.get("idempotency_key") or "")
            if key and key in seen_idempotency:
                self.reject(rejects, "usage", event_id, "DUPLICATE_IDEMPOTENCY_KEY")
                continue
            discount = self._discount(raw, plan_id, event_id, rejects)
            if discount is False:
                continue
            seen_usage.add(event_id)
            if key:
                seen_idempotency.add(key)
            unit_price = _optional_int(raw.get("unit_price_cents")) or int(plan["unit_price_cents"])
            gross = units * unit_price
            percent = int(discount["percent_bps"]) if isinstance(discount, dict) else 0
            discount_cents = gross * percent // 10000
            tax_rate = int(plan.get("tax_rate_basis_points", 0) or 0)
            tax_cents = (gross - discount_cents) * tax_rate // 10000
            net = gross - discount_cents + tax_cents
            accepted.append(
                {
                    "event_id": event_id,
                    "account_id": account_id,
                    "plan_id": plan_id,
                    "units": units,
                    "currency": currency,
                    "gross_cents": gross,
                    "discount_cents": discount_cents,
                    "tax_cents": tax_cents,
                    "net_cents": net,
                    "usd_net_micros": self.usd_micros(net, currency),
                    "source": str(raw.get("source") or ("legacy" if raw.get("version") == 1 else "meter")),
                    "occurred_at": timestamp,
                    "recognition_month": timestamp[:7],
                }
            )
        accepted.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
        return accepted

    def _discount(
        self,
        raw: dict[str, object],
        plan_id: str,
        event_id: str,
        rejects: list[dict[str, str]],
    ) -> dict[str, str] | bool | None:
        code = str(raw.get("discount_code") or "")
        if not code:
            return None
        discount = self.discounts.get(code)
        if discount is None:
            self.reject(rejects, "usage", event_id, "UNKNOWN_DISCOUNT")
            return False
        applies_to = discount.get("applies_to_plan", "")
        if applies_to and applies_to != plan_id:
            self.reject(rejects, "usage", event_id, "DISCOUNT_PLAN_MISMATCH")
            return False
        return discount

    def accepted_amounts(
        self,
        path: Path,
        id_field: str,
        input_name: str,
        timestamp_field: str,
        rejects: list[dict[str, str]],
    ) -> list[dict[str, object]]:
        accepted: list[dict[str, object]] = []
        for raw in _read_optional_csv(path):
            event_id = raw[id_field]
            timestamp = raw[timestamp_field]
            account_id = raw["account_id"]
            account, status, _ = self.effective_account(account_id, timestamp)
            if account is None:
                self.reject(rejects, input_name, event_id, "UNKNOWN_ACCOUNT")
                continue
            if status != "active":
                self.reject(rejects, input_name, event_id, "SUSPENDED_ACCOUNT")
                continue
            currency = raw["currency"]
            if currency not in self.rates:
                self.reject(rejects, input_name, event_id, "UNKNOWN_CURRENCY")
                continue
            amount = _optional_int(raw.get("amount_cents"))
            if amount is None or amount == 0:
                self.reject(rejects, input_name, event_id, "INVALID_AMOUNT")
                continue
            accepted.append(
                {
                    "account_id": account_id,
                    "currency": currency,
                    "event_id": event_id,
                    "amount_cents": amount,
                    "timestamp": timestamp,
                    "recognition_month": timestamp[:7],
                }
            )
        accepted.sort(key=lambda row: (row["timestamp"], row["event_id"]))
        return accepted

    def ledger_rows(
        self,
        usage: list[dict[str, object]],
        adjustments: list[dict[str, object]],
        credits: list[dict[str, object]],
    ) -> list[dict[str, str]]:
        usage_by_key = _group(usage)
        adjustment_by_key = _group(adjustments)
        credit_by_key = _group(credits)
        rows: list[dict[str, str]] = []
        for account_id, currency in sorted(set(usage_by_key) | set(adjustment_by_key) | set(credit_by_key)):
            balance = 0
            balance_usd = 0
            for row in usage_by_key[(account_id, currency)]:
                amount = int(row["net_cents"])
                usd = int(row["usd_net_micros"])
                balance += amount
                balance_usd += usd
                rows.append(_ledger_row(account_id, currency, str(row["event_id"]), "usage", amount, usd, balance, balance_usd, str(row["recognition_month"])))
            for row in adjustment_by_key[(account_id, currency)]:
                amount = int(row["amount_cents"])
                usd = self.usd_micros(amount, currency)
                balance += amount
                balance_usd += usd
                rows.append(_ledger_row(account_id, currency, str(row["event_id"]), "adjustment", amount, usd, balance, balance_usd, str(row["recognition_month"])))
            for row in credit_by_key[(account_id, currency)]:
                requested = max(0, int(row["amount_cents"]))
                amount = -min(requested, max(0, balance))
                usd = self.usd_micros(amount, currency)
                balance += amount
                balance_usd += usd
                rows.append(_ledger_row(account_id, currency, str(row["event_id"]), "credit", amount, usd, balance, balance_usd, str(row["recognition_month"])))
        return rows

    def balance_rows(self, ledger: list[dict[str, str]]) -> list[dict[str, str]]:
        latest: dict[tuple[str, str], dict[str, str]] = {}
        for row in ledger:
            latest[(row["account_id"], row["currency"])] = row
        rows: list[dict[str, str]] = []
        for account_id, currency in sorted(latest):
            account = self.accounts[account_id]
            last = latest[(account_id, currency)]
            rows.append(
                {
                    "account_id": account_id,
                    "region": account.get("region") or "unknown",
                    "segment": account.get("segment") or "unknown",
                    "currency": currency,
                    "ending_balance_cents": last["running_balance_cents"],
                    "ending_balance_usd_micros": last["running_balance_usd_micros"],
                    "status": self.final_status(account_id),
                }
            )
        return rows

    def plan_revenue_rows(self, usage: list[dict[str, object]]) -> list[dict[str, str]]:
        grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
            lambda: {
                "gross_cents": 0,
                "discount_cents": 0,
                "tax_cents": 0,
                "net_cents": 0,
                "net_usd_micros": 0,
            }
        )
        for row in usage:
            key = (str(row["recognition_month"]), str(row["plan_id"]), str(row["currency"]))
            bucket = grouped[key]
            bucket["gross_cents"] += int(row["gross_cents"])
            bucket["discount_cents"] += int(row["discount_cents"])
            bucket["tax_cents"] += int(row["tax_cents"])
            bucket["net_cents"] += int(row["net_cents"])
            bucket["net_usd_micros"] += int(row["usd_net_micros"])
        return [
            {
                "recognition_month": month,
                "plan_id": plan_id,
                "currency": currency,
                **{field: str(value) for field, value in grouped[(month, plan_id, currency)].items()},
            }
            for month, plan_id, currency in sorted(grouped)
        ]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _read_optional_csv(path: Path) -> list[dict[str, str]]:
    return _read_csv(path) if path.exists() else []


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _optional_int(value: object) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        text = str(value)
        if not text or text.strip() != text:
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def _positive_int(value: object) -> int | None:
    integer = _optional_int(value)
    return integer if integer is not None and integer > 0 else None


def _round_half_up(numerator: int, denominator: int = 100) -> int:
    sign = -1 if numerator < 0 else 1
    return sign * ((abs(numerator) + denominator // 2) // denominator)


def _group(rows: list[dict[str, object]]) -> defaultdict[tuple[str, str], list[dict[str, object]]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["account_id"]), str(row["currency"]))].append(row)
    return grouped


def _ledger_row(
    account_id: str,
    currency: str,
    event_id: str,
    event_type: str,
    amount_cents: int,
    amount_usd_micros: int,
    running_balance_cents: int,
    running_balance_usd_micros: int,
    recognition_month: str,
) -> dict[str, str]:
    return {
        "account_id": account_id,
        "currency": currency,
        "event_id": event_id,
        "event_type": event_type,
        "amount_cents": str(amount_cents),
        "amount_usd_micros": str(amount_usd_micros),
        "running_balance_cents": str(running_balance_cents),
        "running_balance_usd_micros": str(running_balance_usd_micros),
        "recognition_month": recognition_month,
    }


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps({field: row[field] for field in fields}, sort_keys=True) + "\n")


def _write_compat_summary(
    path: Path,
    usage: list[dict[str, object]],
    ledger: list[dict[str, str]],
    rejects: list[dict[str, str]],
) -> None:
    summary = {
        "usage_events": len(usage),
        "adjustment_events": sum(1 for row in ledger if row["event_type"] == "adjustment"),
        "credit_events": sum(1 for row in ledger if row["event_type"] == "credit"),
        "reject_count": len(rejects),
        "gross_cents": sum(int(row["gross_cents"]) for row in usage),
        "adjustment_cents": sum(int(row["amount_cents"]) for row in ledger if row["event_type"] == "adjustment"),
        "credit_cents": sum(int(row["amount_cents"]) for row in ledger if row["event_type"] == "credit"),
        "net_cents": sum(int(row["amount_cents"]) for row in ledger),
    }
    path.write_text(json.dumps(summary, sort_keys=True) + "\n")
PY

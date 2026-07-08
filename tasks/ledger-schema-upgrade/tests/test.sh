#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

APP_DIR="$APP_DIR" python3 - <<'PY'
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest


APP_DIR = Path(os.environ["APP_DIR"])

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


def write_hidden(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "accounts.csv").write_text(
        "account_id,status,plan_id,region,segment\n"
        "acct_a,active,basic,na,smb\n"
        "acct_b,active,pro,eu,enterprise\n"
        "acct_c,suspended,basic,na,smb\n"
        "acct_d,active,growth,apac,midmarket\n"
    )
    (root / "plans.json").write_text(
        json.dumps(
            [
                {
                    "plan_id": "basic",
                    "currency": "USD",
                    "unit_price_cents": 100,
                    "tax_rate_basis_points": 500,
                    "recognition_rule": "event_month",
                },
                {
                    "plan_id": "pro",
                    "currency": "EUR",
                    "unit_price_cents": 250,
                    "tax_rate_basis_points": 800,
                    "recognition_rule": "event_month",
                },
                {
                    "plan_id": "growth",
                    "currency": "GBP",
                    "unit_price_cents": 400,
                    "tax_rate_basis_points": 0,
                    "recognition_rule": "event_month",
                },
            ],
            indent=2,
        )
        + "\n"
    )
    (root / "exchange_rates.csv").write_text(
        "currency,to_usd_rate_micros\nUSD,1000000\nEUR,1200000\nGBP,1300000\n"
    )
    (root / "discounts.csv").write_text(
        "discount_code,percent_bps,applies_to_plan\nDISC10,1000,pro\nBASIC5,500,basic\n"
    )
    (root / "account_overrides.csv").write_text(
        "account_id,status_override,plan_override_id,effective_at\n"
        "acct_a,suspended,,2026-01-15T00:00:00Z\n"
        "acct_b,,basic,2026-01-10T00:00:00Z\n"
    )
    usage_rows = [
        {
            "version": 1,
            "usage_id": "u1",
            "account_id": "acct_a",
            "units": 3,
            "occurred_at": "2026-01-02T00:00:00Z",
        },
        {
            "version": 2,
            "usage_id": "u2",
            "account_id": "acct_b",
            "plan_id": "pro",
            "units": 2,
            "occurred_at": "2026-01-02T01:00:00Z",
            "source": "api",
            "discount_code": "DISC10",
        },
        {
            "version": 3,
            "usage_id": "u3",
            "account_id": "acct_d",
            "quantity": 1,
            "unit_price_cents": 450,
            "occurred_at": "2026-01-03T00:00:00Z",
            "source": "meter",
            "idempotency_key": "idem-growth",
        },
        {
            "version": 3,
            "usage_id": "u4",
            "account_id": "acct_a",
            "plan_id": "basic",
            "quantity": 2,
            "occurred_at": "2026-01-04T00:00:00Z",
            "discount_code": "NOPE",
        },
        {
            "version": 1,
            "usage_id": "u1",
            "account_id": "acct_a",
            "units": 1,
            "occurred_at": "2026-01-05T00:00:00Z",
        },
        {
            "version": 3,
            "usage_id": "u6",
            "account_id": "acct_d",
            "quantity": 2,
            "occurred_at": "2026-01-06T00:00:00Z",
            "idempotency_key": "idem-growth",
        },
        {
            "version": 1,
            "usage_id": "u7",
            "account_id": "acct_c",
            "units": 1,
            "occurred_at": "2026-01-07T00:00:00Z",
        },
        {
            "version": 1,
            "usage_id": "u8",
            "account_id": "acct_a",
            "units": 1,
            "occurred_at": "2026-01-20T00:00:00Z",
        },
        {
            "version": 2,
            "usage_id": "u9",
            "account_id": "acct_d",
            "plan_id": "missing",
            "units": 1,
            "occurred_at": "2026-01-08T00:00:00Z",
        },
        {
            "version": 1,
            "usage_id": "u10",
            "account_id": "acct_b",
            "units": 0,
            "occurred_at": "2026-01-09T00:00:00Z",
        },
        {
            "version": 1,
            "usage_id": "u11",
            "account_id": "acct_b",
            "units": 4,
            "occurred_at": "2026-01-20T00:00:00Z",
        },
    ]
    (root / "usage.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in usage_rows)
    )
    (root / "legacy_adjustments.csv").write_text(
        "adjustment_id,account_id,currency,amount_cents,reason,effective_at\n"
        "a1,acct_a,USD,-25,manual,2026-01-05T00:00:00Z\n"
        "a2,acct_d,GBP,50,manual,2026-01-05T00:00:00Z\n"
        "a3,acct_c,USD,10,manual,2026-01-05T00:00:00Z\n"
        "a4,acct_b,EUR,10,manual,2026-01-06T00:00:00Z\n"
    )
    (root / "credits.csv").write_text(
        "credit_id,account_id,currency,amount_cents,issued_at,reason\n"
        "c1,acct_a,USD,200,2026-01-10T00:00:00Z,promo\n"
        "c2,acct_a,USD,200,2026-01-20T00:00:00Z,promo\n"
        "c3,acct_b,USD,100,2026-01-25T00:00:00Z,promo\n"
        "c4,acct_b,EUR,100,2026-01-05T00:00:00Z,promo\n"
        "c_missing,acct_missing,USD,100,2026-01-05T00:00:00Z,promo\n"
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def optional_csv(path: Path) -> list[dict[str, str]]:
    return read_csv(path) if path.exists() else []


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def as_int(value: object) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        text = str(value)
        if text.strip() != text or text == "":
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def positive_int(value: object) -> int | None:
    integer = as_int(value)
    return integer if integer is not None and integer > 0 else None


def round_half_up(numerator: int, denominator: int = 100) -> int:
    sign = -1 if numerator < 0 else 1
    return sign * ((abs(numerator) + denominator // 2) // denominator)


class ReferencePackage:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.accounts = {row["account_id"]: row for row in read_csv(source / "accounts.csv")}
        self.plans = {row["plan_id"]: row for row in json.loads((source / "plans.json").read_text())}
        self.rates = {"USD": 1000000}
        for row in optional_csv(source / "exchange_rates.csv"):
            self.rates[row["currency"]] = int(row["to_usd_rate_micros"])
        self.discounts = {
            row["discount_code"]: row for row in optional_csv(source / "discounts.csv")
        }
        self.overrides = optional_csv(source / "account_overrides.csv")

    def account_at(self, account_id: str, timestamp: str) -> tuple[dict[str, str] | None, str, str]:
        account = self.accounts.get(account_id)
        if account is None:
            return None, "", ""
        status = account.get("status", "")
        plan_id = account.get("plan_id", "")
        for row in sorted(self.overrides, key=lambda item: item["effective_at"]):
            if row["account_id"] != account_id or row["effective_at"] > timestamp:
                continue
            if row.get("status_override"):
                status = row["status_override"]
            if row.get("plan_override_id"):
                plan_id = row["plan_override_id"]
        return account, status, plan_id

    def final_status(self, account_id: str) -> str:
        account = self.accounts[account_id]
        status = account["status"]
        for row in sorted(self.overrides, key=lambda item: item["effective_at"]):
            if row["account_id"] == account_id and row.get("status_override"):
                status = row["status_override"]
        return status

    def usd_micros(self, amount_cents: int, currency: str) -> int:
        return round_half_up(amount_cents * self.rates[currency])

    def reject(self, rows: list[dict[str, str]], input_name: str, event_id: str, reason: str) -> None:
        rows.append({"input": input_name, "event_id": event_id, "reason": reason})

    def usage(self, rejects: list[dict[str, str]]) -> list[dict[str, object]]:
        accepted: list[dict[str, object]] = []
        seen_usage: set[str] = set()
        seen_keys: set[str] = set()
        for raw in read_jsonl(self.source / "usage.jsonl"):
            event_id = str(raw.get("usage_id") or "")
            timestamp = str(raw.get("occurred_at") or "")
            account_id = str(raw.get("account_id") or "")
            account, status, account_plan = self.account_at(account_id, timestamp)
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
            units = positive_int(raw.get("quantity", raw.get("units")))
            if units is None:
                self.reject(rejects, "usage", event_id, "INVALID_UNITS")
                continue
            if event_id in seen_usage:
                self.reject(rejects, "usage", event_id, "DUPLICATE_USAGE_ID")
                continue
            idempotency_key = str(raw.get("idempotency_key") or "")
            if idempotency_key and idempotency_key in seen_keys:
                self.reject(rejects, "usage", event_id, "DUPLICATE_IDEMPOTENCY_KEY")
                continue
            discount_code = str(raw.get("discount_code") or "")
            discount = None
            if discount_code:
                discount = self.discounts.get(discount_code)
                if discount is None:
                    self.reject(rejects, "usage", event_id, "UNKNOWN_DISCOUNT")
                    continue
                applies_to = discount.get("applies_to_plan", "")
                if applies_to and applies_to != plan_id:
                    self.reject(rejects, "usage", event_id, "DISCOUNT_PLAN_MISMATCH")
                    continue
            seen_usage.add(event_id)
            if idempotency_key:
                seen_keys.add(idempotency_key)
            unit_price = as_int(raw.get("unit_price_cents")) or int(plan["unit_price_cents"])
            gross = units * unit_price
            percent = int(discount["percent_bps"]) if discount else 0
            discount_cents = gross * percent // 10000
            tax_cents = (gross - discount_cents) * int(plan.get("tax_rate_basis_points", 0)) // 10000
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

    def money_rows(
        self,
        path: Path,
        id_field: str,
        input_name: str,
        timestamp_field: str,
        rejects: list[dict[str, str]],
    ) -> list[dict[str, object]]:
        accepted: list[dict[str, object]] = []
        for raw in optional_csv(path):
            event_id = raw[id_field]
            timestamp = raw[timestamp_field]
            account_id = raw["account_id"]
            account, status, _ = self.account_at(account_id, timestamp)
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
            amount = as_int(raw.get("amount_cents"))
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

    def package(self) -> dict[str, object]:
        rejects: list[dict[str, str]] = []
        usage = self.usage(rejects)
        adjustments = self.money_rows(
            self.source / "legacy_adjustments.csv",
            "adjustment_id",
            "adjustment",
            "effective_at",
            rejects,
        )
        credits = self.money_rows(
            self.source / "credits.csv",
            "credit_id",
            "credit",
            "issued_at",
            rejects,
        )
        ledger = self.ledger(usage, adjustments, credits)
        balances = self.balances(ledger)
        plan_revenue = self.plan_revenue(usage)
        rejects.sort(key=lambda row: (row["input"], row["event_id"]))
        audit = {
            "schema_version": "v4",
            "source_files": sorted(path.name for path in self.source.iterdir() if path.is_file()),
            "normalized_events": len(usage),
            "ledger_rows": len(ledger),
            "account_balance_rows": len(balances),
            "plan_revenue_rows": len(plan_revenue),
            "reject_count": len(rejects),
            "currencies": sorted({row["currency"] for row in ledger}),
            "net_usd_micros": sum(int(row["amount_usd_micros"]) for row in ledger),
            "generated_at": "deterministic",
        }
        return {
            "normalized_events.jsonl": usage,
            "ledger.csv": ledger,
            "account_balances.csv": balances,
            "plan_revenue.csv": plan_revenue,
            "rejects.csv": rejects,
            "migration_audit.json": audit,
        }

    def ledger(
        self,
        usage: list[dict[str, object]],
        adjustments: list[dict[str, object]],
        credits: list[dict[str, object]],
    ) -> list[dict[str, str]]:
        grouped_usage: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        grouped_adjustments: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        grouped_credits: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for row in usage:
            grouped_usage[(str(row["account_id"]), str(row["currency"]))].append(row)
        for row in adjustments:
            grouped_adjustments[(str(row["account_id"]), str(row["currency"]))].append(row)
        for row in credits:
            grouped_credits[(str(row["account_id"]), str(row["currency"]))].append(row)

        rows: list[dict[str, str]] = []
        for key in sorted(set(grouped_usage) | set(grouped_adjustments) | set(grouped_credits)):
            account_id, currency = key
            balance = 0
            balance_usd = 0
            for row in grouped_usage[key]:
                amount = int(row["net_cents"])
                usd = int(row["usd_net_micros"])
                balance += amount
                balance_usd += usd
                rows.append(self.ledger_row(account_id, currency, str(row["event_id"]), "usage", amount, usd, balance, balance_usd, str(row["recognition_month"])))
            for row in grouped_adjustments[key]:
                amount = int(row["amount_cents"])
                usd = self.usd_micros(amount, currency)
                balance += amount
                balance_usd += usd
                rows.append(self.ledger_row(account_id, currency, str(row["event_id"]), "adjustment", amount, usd, balance, balance_usd, str(row["recognition_month"])))
            for row in grouped_credits[key]:
                requested = max(0, int(row["amount_cents"]))
                amount = -min(requested, max(0, balance))
                usd = self.usd_micros(amount, currency)
                balance += amount
                balance_usd += usd
                rows.append(self.ledger_row(account_id, currency, str(row["event_id"]), "credit", amount, usd, balance, balance_usd, str(row["recognition_month"])))
        return rows

    def ledger_row(
        self,
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

    def balances(self, ledger: list[dict[str, str]]) -> list[dict[str, str]]:
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

    def plan_revenue(self, usage: list[dict[str, object]]) -> list[dict[str, str]]:
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
            for field in bucket:
                source_field = "usd_net_micros" if field == "net_usd_micros" else field
                bucket[field] += int(row[source_field])
        return [
            {
                "recognition_month": month,
                "plan_id": plan_id,
                "currency": currency,
                **{field: str(value) for field, value in grouped[(month, plan_id, currency)].items()},
            }
            for month, plan_id, currency in sorted(grouped)
        ]


class HiddenLedgerV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        write_hidden(self.input_dir)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(APP_DIR)
        subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(APP_DIR / "tests")],
            check=True,
            cwd=APP_DIR,
            env=env,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "ledger_migrator.cli",
                "--input-dir",
                str(self.input_dir),
                "--output-dir",
                str(self.output_dir),
            ],
            check=True,
            cwd=APP_DIR,
            env=env,
        )
        self.expected = ReferencePackage(self.input_dir).package()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_jsonl_schema_and_values(self) -> None:
        actual = read_jsonl(self.output_dir / "normalized_events.jsonl")
        self.assertEqual(actual, self.expected["normalized_events.jsonl"])
        self.assertEqual(set(actual[0]), set(NORMALIZED_FIELDS))

    def test_csv_outputs_match_reference(self) -> None:
        for filename, fields in [
            ("ledger.csv", LEDGER_FIELDS),
            ("account_balances.csv", BALANCE_FIELDS),
            ("plan_revenue.csv", PLAN_FIELDS),
            ("rejects.csv", REJECT_FIELDS),
        ]:
            with self.subTest(filename=filename):
                actual = read_csv(self.output_dir / filename)
                self.assertEqual(list(actual[0]), fields)
                self.assertEqual(actual, self.expected[filename])

    def test_migration_audit_matches_reference(self) -> None:
        actual = json.loads((self.output_dir / "migration_audit.json").read_text())
        self.assertEqual(actual, self.expected["migration_audit.json"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenLedgerV4Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

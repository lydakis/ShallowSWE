#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/build_outputs.py" <<'PY'
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import json


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def money_to_cents(amount: str, rate: str) -> int:
    return int(
        (Decimal(amount) * Decimal(rate) * Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def cents_to_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def add_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def period(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def allocate_cents(total_cents: int, start: date, end: date) -> list[tuple[str, int]]:
    total_days = (end - start).days + 1
    cursor = month_start(start)
    touched: list[tuple[str, int]] = []
    while cursor <= end:
        month_end = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
        overlap_start = max(start, cursor)
        overlap_end = min(end, month_end)
        if overlap_start <= overlap_end:
            touched.append((period(cursor), (overlap_end - overlap_start).days + 1))
        cursor = add_month(cursor)
    allocated: list[tuple[str, int]] = []
    used = 0
    for index, (month, days) in enumerate(touched):
        if index == len(touched) - 1:
            cents = total_cents - used
        else:
            cents = total_cents * days // total_days
            used += cents
        allocated.append((month, cents))
    return allocated


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sum_money(rows: list[dict[str, str]], key: str) -> int:
    total = 0
    for row in rows:
        total += money_to_cents(row[key], "1")
    return total


def main() -> None:
    root = Path.cwd()
    input_dir = root / "input"
    output_dir = root / "output"
    output_dir.mkdir(exist_ok=True)

    accounts = {row["account_id"]: row for row in read_csv(input_dir / "accounts.csv")}
    contracts = {row["account_id"]: row for row in read_csv(input_dir / "contracts.csv")}
    rates = {row["currency"]: row["rate_to_usd"] for row in read_csv(input_dir / "fx_rates.csv")}
    invoices = {row["invoice_id"]: row for row in read_csv(input_dir / "invoices.csv")}
    credits = read_csv(input_dir / "credits.csv")
    disputes = read_csv(input_dir / "disputes.csv")
    payments = read_csv(input_dir / "payments.csv")
    paid_invoices = {key: row for key, row in invoices.items() if row["status"] == "paid"}

    rollup: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"gross": 0, "credits": 0, "disputes": 0}
    )
    accounts_work: dict[str, dict[str, int]] = defaultdict(
        lambda: {"recognized": 0, "disputes": 0, "payments": 0, "open_ar": 0}
    )
    invoice_gross: dict[str, int] = {}
    invoice_credits: dict[str, int] = defaultdict(int)
    invoice_payments: dict[str, int] = defaultdict(int)
    adjustments: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []

    for invoice_id, invoice in paid_invoices.items():
        gross = money_to_cents(invoice["amount"], rates[invoice["currency"]])
        invoice_gross[invoice_id] = gross
        start = date.fromisoformat(invoice["service_start"])
        end = date.fromisoformat(invoice["service_end"])
        for revenue_period, cents in allocate_cents(gross, start, end):
            rollup[(revenue_period, invoice["plan"])]["gross"] += cents
            accounts_work[invoice["account_id"]]["recognized"] += cents

    for credit in credits:
        invoice = invoices.get(credit["invoice_id"])
        if invoice is None:
            rejects.append({"input": "credit", "event_id": credit["credit_id"], "reason": "unknown_invoice"})
            continue
        if invoice["status"] != "paid":
            rejects.append({"input": "credit", "event_id": credit["credit_id"], "reason": "invoice_not_paid"})
            continue
        cents = money_to_cents(credit["amount"], rates[credit["currency"]])
        credit_period = period(date.fromisoformat(credit["issued_at"]))
        rollup[(credit_period, invoice["plan"])]["credits"] += cents
        accounts_work[invoice["account_id"]]["recognized"] -= cents
        invoice_credits[credit["invoice_id"]] += cents
        adjustments.append(
            {
                "adjustment_id": credit["credit_id"],
                "invoice_id": credit["invoice_id"],
                "account_id": invoice["account_id"],
                "type": "credit",
                "amount_usd": cents_to_money(cents),
                "status": "applied",
                "period": credit_period,
            }
        )

    for dispute in disputes:
        if dispute["status"] != "open":
            continue
        invoice = invoices.get(dispute["invoice_id"])
        if invoice is None:
            rejects.append({"input": "dispute", "event_id": dispute["dispute_id"], "reason": "unknown_invoice"})
            continue
        if invoice["status"] != "paid":
            rejects.append({"input": "dispute", "event_id": dispute["dispute_id"], "reason": "invoice_not_paid"})
            continue
        cents = money_to_cents(dispute["amount"], rates[dispute["currency"]])
        dispute_period = period(date.fromisoformat(dispute["opened_at"]))
        rollup[(dispute_period, invoice["plan"])]["disputes"] += cents
        accounts_work[invoice["account_id"]]["disputes"] += cents
        adjustments.append(
            {
                "adjustment_id": dispute["dispute_id"],
                "invoice_id": dispute["invoice_id"],
                "account_id": invoice["account_id"],
                "type": "dispute",
                "amount_usd": cents_to_money(cents),
                "status": "open",
                "period": dispute_period,
            }
        )

    for payment in payments:
        if payment["status"] != "settled":
            continue
        invoice = invoices.get(payment["invoice_id"])
        if invoice is None:
            rejects.append({"input": "payment", "event_id": payment["payment_id"], "reason": "unknown_invoice"})
            continue
        if invoice["status"] != "paid":
            rejects.append({"input": "payment", "event_id": payment["payment_id"], "reason": "invoice_not_paid"})
            continue
        cents = money_to_cents(payment["amount"], rates[payment["currency"]])
        invoice_payments[payment["invoice_id"]] += cents
        accounts_work[invoice["account_id"]]["payments"] += cents

    revenue_rows = []
    for (revenue_period, plan), values in sorted(rollup.items()):
        revenue_rows.append(
            {
                "period": revenue_period,
                "plan": plan,
                "gross_usd": cents_to_money(values["gross"]),
                "credits_usd": cents_to_money(values["credits"]),
                "open_disputes_usd": cents_to_money(values["disputes"]),
                "net_usd": cents_to_money(values["gross"] - values["credits"]),
            }
        )

    exposure_rows = []
    for account_id in sorted(accounts_work):
        totals = accounts_work[account_id]
        if totals["recognized"] == 0 and totals["disputes"] == 0:
            continue
        account = accounts[account_id]
        disputed = totals["disputes"] > 0
        exposure_rows.append(
            {
                "account_id": account_id,
                "segment": account["segment"],
                "region": account["region"],
                "manager": account["manager"],
                "recognized_usd": cents_to_money(totals["recognized"]),
                "open_disputes_usd": cents_to_money(totals["disputes"]),
                "net_at_risk_usd": cents_to_money(totals["recognized"] if disputed else 0),
                "status": "disputed" if disputed else "clear",
            }
        )

    cash_rows = []
    for invoice_id, invoice in sorted(paid_invoices.items(), key=lambda item: (item[1]["account_id"], item[0])):
        invoice_net = invoice_gross[invoice_id] - invoice_credits[invoice_id]
        settled = invoice_payments[invoice_id]
        open_ar = max(invoice_net - settled, 0)
        accounts_work[invoice["account_id"]]["open_ar"] += open_ar
        cash_rows.append(
            {
                "account_id": invoice["account_id"],
                "invoice_id": invoice_id,
                "period": period(date.fromisoformat(invoice["invoice_date"])),
                "invoice_net_usd": cents_to_money(invoice_net),
                "settled_payments_usd": cents_to_money(settled),
                "open_ar_usd": cents_to_money(open_ar),
                "status": "paid_in_full" if open_ar == 0 else "open",
            }
        )

    contract_rows = []
    for account_id in sorted(set(contracts) | {row["account_id"] for row in exposure_rows}):
        account = accounts[account_id]
        contract = contracts.get(account_id)
        contracted = 0
        contract_id = ""
        if contract is not None:
            contract_id = contract["contract_id"]
            contracted = money_to_cents(contract["committed_amount"], rates[contract["currency"]])
        recognized = accounts_work[account_id]["recognized"]
        payments_cents = accounts_work[account_id]["payments"]
        open_ar = accounts_work[account_id]["open_ar"]
        variance = recognized - contracted
        contract_rows.append(
            {
                "account_id": account_id,
                "contract_id": contract_id,
                "manager": account["manager"],
                "contracted_usd": cents_to_money(contracted),
                "net_recognized_usd": cents_to_money(recognized),
                "settled_payments_usd": cents_to_money(payments_cents),
                "open_ar_usd": cents_to_money(open_ar),
                "variance_usd": cents_to_money(variance),
                "status": "under_committed" if variance < 0 else "over_committed" if variance > 0 else "on_target",
            }
        )

    adjustments.sort(key=lambda row: (row["period"], row["type"], row["adjustment_id"]))
    rejects.sort(key=lambda row: (row["input"], row["event_id"]))

    write_csv(
        output_dir / "revenue_rollup.csv",
        ["period", "plan", "gross_usd", "credits_usd", "open_disputes_usd", "net_usd"],
        revenue_rows,
    )
    write_csv(
        output_dir / "account_exposure.csv",
        [
            "account_id",
            "segment",
            "region",
            "manager",
            "recognized_usd",
            "open_disputes_usd",
            "net_at_risk_usd",
            "status",
        ],
        exposure_rows,
    )
    write_csv(
        output_dir / "adjustments.csv",
        ["adjustment_id", "invoice_id", "account_id", "type", "amount_usd", "status", "period"],
        adjustments,
    )
    write_csv(
        output_dir / "cash_application.csv",
        ["account_id", "invoice_id", "period", "invoice_net_usd", "settled_payments_usd", "open_ar_usd", "status"],
        cash_rows,
    )
    write_csv(
        output_dir / "contract_variance.csv",
        [
            "account_id",
            "contract_id",
            "manager",
            "contracted_usd",
            "net_recognized_usd",
            "settled_payments_usd",
            "open_ar_usd",
            "variance_usd",
            "status",
        ],
        contract_rows,
    )
    write_csv(output_dir / "rejects.csv", ["input", "event_id", "reason"], rejects)

    summary = {
        "accounts_at_risk": sum(row["status"] == "disputed" for row in exposure_rows),
        "credits_usd": cents_to_money(sum(values["credits"] for values in rollup.values())),
        "gross_revenue_usd": cents_to_money(sum(values["gross"] for values in rollup.values())),
        "net_revenue_usd": cents_to_money(sum(values["gross"] - values["credits"] for values in rollup.values())),
        "open_disputes": sum(1 for row in adjustments if row["type"] == "dispute"),
        "open_disputes_usd": cents_to_money(sum(values["disputes"] for values in rollup.values())),
        "open_ar_usd": cents_to_money(sum_money(cash_rows, "open_ar_usd")),
        "settled_payments_usd": cents_to_money(sum(accounts_work[account]["payments"] for account in accounts_work)),
        "contracted_usd": cents_to_money(
            sum(money_to_cents(row["committed_amount"], rates[row["currency"]]) for row in contracts.values())
        ),
        "contract_variance_usd": cents_to_money(sum_money(contract_rows, "variance_usd")),
        "periods": sorted({row["period"] for row in revenue_rows}),
        "plans": sorted({row["plan"] for row in revenue_rows}),
        "rejected_adjustments": len(rejects),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    close_audit = {
        "generated_at": "deterministic",
        "input_rows": {
            "accounts": len(accounts),
            "contracts": len(contracts),
            "invoices": len(invoices),
            "credits": len(credits),
            "disputes": len(disputes),
            "payments": len(payments),
        },
        "output_rows": {
            "revenue_rollup": len(revenue_rows),
            "account_exposure": len(exposure_rows),
            "adjustments": len(adjustments),
            "cash_application": len(cash_rows),
            "contract_variance": len(contract_rows),
            "rejects": len(rejects),
        },
        "control_totals": {
            "gross_revenue_usd": summary["gross_revenue_usd"],
            "credits_usd": summary["credits_usd"],
            "net_revenue_usd": summary["net_revenue_usd"],
            "settled_payments_usd": summary["settled_payments_usd"],
            "open_ar_usd": summary["open_ar_usd"],
            "contracted_usd": summary["contracted_usd"],
            "contract_variance_usd": summary["contract_variance_usd"],
        },
        "periods": summary["periods"],
        "plans": summary["plans"],
    }
    (output_dir / "close_audit.json").write_text(json.dumps(close_audit, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/build_outputs.py

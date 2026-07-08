#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

app = Path(os.environ.get("APP_DIR", "/app"))
OUTPUT_FILES = {
    "summary.json",
    "revenue_rollup.csv",
    "account_exposure.csv",
    "adjustments.csv",
    "cash_application.csv",
    "contract_variance.csv",
    "rejects.csv",
    "close_audit.json",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def cents_to_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def money_to_cents(amount: str, rate: str) -> int:
    value = (Decimal(amount) * Decimal(rate) * Decimal("100")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(value)


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


def write_fixture(root: Path, files: dict[str, str]) -> None:
    input_dir = root / "input"
    input_dir.mkdir(parents=True)
    for name, content in files.items():
        (input_dir / name).write_text(content)


def expected(root: Path) -> dict[str, object]:
    input_dir = root / "input"
    accounts = {row["account_id"]: row for row in read_csv(input_dir / "accounts.csv")}
    contracts = {row["account_id"]: row for row in read_csv(input_dir / "contracts.csv")}
    rates = {row["currency"]: row["rate_to_usd"] for row in read_csv(input_dir / "fx_rates.csv")}
    invoices = {row["invoice_id"]: row for row in read_csv(input_dir / "invoices.csv")}
    paid = {invoice_id: row for invoice_id, row in invoices.items() if row["status"] == "paid"}

    rollup: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"gross": 0, "credits": 0, "disputes": 0}
    )
    account_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"recognized": 0, "disputes": 0, "payments": 0, "open_ar": 0}
    )
    invoice_gross: dict[str, int] = {}
    invoice_credits: dict[str, int] = defaultdict(int)
    invoice_payments: dict[str, int] = defaultdict(int)
    adjustments: list[dict[str, str]] = []
    rejects: list[dict[str, str]] = []

    for invoice_id, invoice in paid.items():
        gross = money_to_cents(invoice["amount"], rates[invoice["currency"]])
        invoice_gross[invoice_id] = gross
        start = date.fromisoformat(invoice["service_start"])
        end = date.fromisoformat(invoice["service_end"])
        for month, cents in allocate_cents(gross, start, end):
            rollup[(month, invoice["plan"])]["gross"] += cents
            account_totals[invoice["account_id"]]["recognized"] += cents

    for credit in read_csv(input_dir / "credits.csv"):
        invoice = invoices.get(credit["invoice_id"])
        if invoice is None:
            rejects.append({"input": "credit", "event_id": credit["credit_id"], "reason": "unknown_invoice"})
            continue
        if invoice["status"] != "paid":
            rejects.append({"input": "credit", "event_id": credit["credit_id"], "reason": "invoice_not_paid"})
            continue
        cents = money_to_cents(credit["amount"], rates[credit["currency"]])
        month = period(date.fromisoformat(credit["issued_at"]))
        rollup[(month, invoice["plan"])]["credits"] += cents
        account_totals[invoice["account_id"]]["recognized"] -= cents
        invoice_credits[credit["invoice_id"]] += cents
        adjustments.append(
            {
                "adjustment_id": credit["credit_id"],
                "invoice_id": credit["invoice_id"],
                "account_id": invoice["account_id"],
                "type": "credit",
                "amount_usd": cents_to_money(cents),
                "status": "applied",
                "period": month,
            }
        )

    for dispute in read_csv(input_dir / "disputes.csv"):
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
        month = period(date.fromisoformat(dispute["opened_at"]))
        rollup[(month, invoice["plan"])]["disputes"] += cents
        account_totals[invoice["account_id"]]["disputes"] += cents
        adjustments.append(
            {
                "adjustment_id": dispute["dispute_id"],
                "invoice_id": dispute["invoice_id"],
                "account_id": invoice["account_id"],
                "type": "dispute",
                "amount_usd": cents_to_money(cents),
                "status": "open",
                "period": month,
            }
        )

    for payment in read_csv(input_dir / "payments.csv"):
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
        account_totals[invoice["account_id"]]["payments"] += cents

    revenue_rows = []
    for (month, plan), values in sorted(rollup.items()):
        net = values["gross"] - values["credits"]
        revenue_rows.append(
            {
                "period": month,
                "plan": plan,
                "gross_usd": cents_to_money(values["gross"]),
                "credits_usd": cents_to_money(values["credits"]),
                "open_disputes_usd": cents_to_money(values["disputes"]),
                "net_usd": cents_to_money(net),
            }
        )

    exposure_rows = []
    for account_id in sorted(account_totals):
        totals = account_totals[account_id]
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
    for invoice_id, invoice in sorted(paid.items(), key=lambda item: (item[1]["account_id"], item[0])):
        net = invoice_gross[invoice_id] - invoice_credits[invoice_id]
        paid_cents = invoice_payments[invoice_id]
        open_ar = max(net - paid_cents, 0)
        account_totals[invoice["account_id"]]["open_ar"] += open_ar
        cash_rows.append(
            {
                "account_id": invoice["account_id"],
                "invoice_id": invoice_id,
                "period": period(date.fromisoformat(invoice["invoice_date"])),
                "invoice_net_usd": cents_to_money(net),
                "settled_payments_usd": cents_to_money(paid_cents),
                "open_ar_usd": cents_to_money(open_ar),
                "status": "paid_in_full" if open_ar == 0 else "open",
            }
        )

    contract_rows = []
    contract_accounts = set(contracts)
    active_accounts = {row["account_id"] for row in exposure_rows} | contract_accounts
    for account_id in sorted(active_accounts):
        account = accounts[account_id]
        contract = contracts.get(account_id)
        contracted = 0 if contract is None else money_to_cents(contract["committed_amount"], rates[contract["currency"]])
        recognized = account_totals[account_id]["recognized"]
        payments = account_totals[account_id]["payments"]
        open_ar = account_totals[account_id]["open_ar"]
        variance = recognized - contracted
        contract_rows.append(
            {
                "account_id": account_id,
                "contract_id": "" if contract is None else contract["contract_id"],
                "manager": account["manager"],
                "contracted_usd": cents_to_money(contracted),
                "net_recognized_usd": cents_to_money(recognized),
                "settled_payments_usd": cents_to_money(payments),
                "open_ar_usd": cents_to_money(open_ar),
                "variance_usd": cents_to_money(variance),
                "status": "under_committed" if variance < 0 else "over_committed" if variance > 0 else "on_target",
            }
        )

    adjustments.sort(key=lambda row: (row["period"], row["type"], row["adjustment_id"]))
    rejects.sort(key=lambda row: (row["input"], row["event_id"]))
    summary = {
        "accounts_at_risk": sum(row["status"] == "disputed" for row in exposure_rows),
        "credits_usd": cents_to_money(sum(values["credits"] for values in rollup.values())),
        "gross_revenue_usd": cents_to_money(sum(values["gross"] for values in rollup.values())),
        "net_revenue_usd": cents_to_money(sum(values["gross"] - values["credits"] for values in rollup.values())),
        "open_disputes": sum(1 for row in adjustments if row["type"] == "dispute"),
        "open_disputes_usd": cents_to_money(sum(values["disputes"] for values in rollup.values())),
        "open_ar_usd": cents_to_money(sum(money_to_cents(row["open_ar_usd"], "1") for row in cash_rows)),
        "settled_payments_usd": cents_to_money(sum(account_totals[account]["payments"] for account in account_totals)),
        "contracted_usd": cents_to_money(
            sum(money_to_cents(row["committed_amount"], rates[row["currency"]]) for row in contracts.values())
        ),
        "contract_variance_usd": cents_to_money(
            sum(money_to_cents(row["variance_usd"], "1") for row in contract_rows)
        ),
        "periods": sorted({row["period"] for row in revenue_rows}),
        "plans": sorted({row["plan"] for row in revenue_rows}),
        "rejected_adjustments": len(rejects),
    }
    close_audit = {
        "generated_at": "deterministic",
        "input_rows": {
            "accounts": len(accounts),
            "contracts": len(contracts),
            "invoices": len(invoices),
            "credits": len(read_csv(input_dir / "credits.csv")),
            "disputes": len(read_csv(input_dir / "disputes.csv")),
            "payments": len(read_csv(input_dir / "payments.csv")),
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
    return {
        "summary.json": summary,
        "close_audit.json": close_audit,
        "revenue_rollup.csv": revenue_rows,
        "account_exposure.csv": exposure_rows,
        "adjustments.csv": adjustments,
        "cash_application.csv": cash_rows,
        "contract_variance.csv": contract_rows,
        "rejects.csv": rejects,
    }


def assert_outputs(root: Path) -> None:
    output_dir = root / "output"
    actual_files = {path.name for path in output_dir.iterdir() if path.is_file()}
    assert actual_files == OUTPUT_FILES, f"output files mismatch: {actual_files}"
    exp = expected(root)
    assert json.loads((output_dir / "summary.json").read_text()) == exp["summary.json"]
    assert json.loads((output_dir / "close_audit.json").read_text()) == exp["close_audit.json"]
    for name in [
        "revenue_rollup.csv",
        "account_exposure.csv",
        "adjustments.csv",
        "cash_application.csv",
        "contract_variance.csv",
        "rejects.csv",
    ]:
        assert read_csv(output_dir / name) == exp[name], name


def run_script(root: Path) -> None:
    subprocess.run([sys.executable, str(root / "scripts" / "build_outputs.py")], cwd=root, check=True)


def copy_script_to_hidden(root: Path) -> None:
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(app / "scripts" / "build_outputs.py", root / "scripts" / "build_outputs.py")
    write_fixture(
        root,
        {
            "accounts.csv": (
                "account_id,segment,region,manager\n"
                "B-1,enterprise,NA,Ada Chen\n"
                "B-2,midmarket,EU,Ben Cruz\n"
                "B-3,growth,APAC,Nia Shah\n"
                "B-4,growth,NA,Ada Chen\n"
            ),
            "contracts.csv": (
                "contract_id,account_id,currency,committed_amount,contract_start,contract_end\n"
                "HCT-1,B-1,USD,330.00,2026-04-01,2026-12-31\n"
                "HCT-2,B-2,EUR,150.00,2026-04-01,2026-12-31\n"
                "HCT-3,B-4,USD,25.00,2026-04-01,2026-12-31\n"
            ),
            "fx_rates.csv": "currency,rate_to_usd\nUSD,1.00\nEUR,1.20\nJPY,0.01\n",
            "invoices.csv": (
                "invoice_id,account_id,plan,currency,amount,status,invoice_date,service_start,service_end\n"
                "H-1,B-1,scale,USD,310.00,paid,2026-04-02,2026-04-01,2026-04-30\n"
                "H-2,B-2,team,EUR,120.00,paid,2026-04-20,2026-04-15,2026-05-14\n"
                "H-3,B-3,starter,JPY,10000,paid,2026-05-01,2026-05-01,2026-05-31\n"
                "H-4,B-2,team,USD,90.00,draft,2026-05-05,2026-05-01,2026-05-31\n"
            ),
            "credits.csv": (
                "credit_id,invoice_id,currency,amount,issued_at,reason\n"
                "HC-1,H-2,EUR,12.00,2026-05-01,discount\n"
                "HC-2,H-4,USD,10.00,2026-05-10,draft_credit\n"
                "HC-3,H-9,USD,5.00,2026-05-10,unknown\n"
            ),
            "disputes.csv": (
                "dispute_id,invoice_id,currency,amount,status,opened_at\n"
                "HD-1,H-1,USD,31.00,open,2026-04-10\n"
                "HD-2,H-2,EUR,20.00,open,2026-05-02\n"
                "HD-3,H-3,JPY,1000,won,2026-05-03\n"
                "HD-4,H-4,USD,9.00,open,2026-05-04\n"
            ),
            "payments.csv": (
                "payment_id,invoice_id,currency,amount,status,received_at\n"
                "HP-1,H-1,USD,310.00,settled,2026-04-05\n"
                "HP-2,H-2,EUR,100.00,settled,2026-05-10\n"
                "HP-3,H-3,JPY,5000,settled,2026-05-12\n"
                "HP-4,H-4,USD,20.00,settled,2026-05-13\n"
                "HP-5,H-404,USD,1.00,settled,2026-05-13\n"
                "HP-6,H-2,EUR,10.00,pending,2026-05-14\n"
            ),
        },
    )


script = app / "scripts" / "build_outputs.py"
assert script.exists(), "missing scripts/build_outputs.py"
run_script(app)
assert_outputs(app)

with tempfile.TemporaryDirectory() as tmp:
    hidden = Path(tmp) / "app"
    copy_script_to_hidden(hidden)
    run_script(hidden)
    assert_outputs(hidden)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

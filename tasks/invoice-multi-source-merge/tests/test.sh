#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


FIELDNAMES = [
    "invoice_id",
    "customer",
    "amount_usd_cents",
    "status",
    "issued_at",
    "updated_at",
    "source",
]
REJECT_FIELDNAMES = ["source", "row_ref", "invoice_id", "reason"]
SOURCE_ORDER = {"api": 0, "csv": 1, "legacy": 2}
PRECEDENCE = {"legacy": 0, "csv": 1, "api": 2}
STATUS = {
    "paid": "paid",
    "settled": "paid",
    "open": "open",
    "pending": "open",
    "draft": "open",
    "void": "void",
    "canceled": "void",
    "cancelled": "void",
}


def normalize_id(value: object) -> str:
    return str(value or "").strip().upper()


def normalize_status(value: object) -> str | None:
    return STATUS.get(str(value or "").strip().lower())


def parse_date(value: str, legacy: bool = False) -> str | None:
    value = str(value or "").strip()
    if legacy:
        if len(value) == 8 and value.isdigit():
            return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
        return None
    parts = value.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return value
    return None


def cents(value: object, currency: object, rates: dict[str, str], *, legacy: bool = False) -> tuple[int | None, str | None]:
    code = str(currency or "").strip().upper()
    if code not in rates:
        return None, "unknown_currency"
    try:
        amount = Decimal(str(value))
        if legacy:
            amount = amount / Decimal("100")
        if amount <= 0:
            return None, "non_positive_amount"
        return int((amount * Decimal(rates[code]) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)), None
    except Exception:
        return None, "non_positive_amount"


def expected(input_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    rates = json.loads((input_dir / "currency_rates.json").read_text())
    records: list[dict[str, object]] = []
    rejects: list[dict[str, str]] = []

    def add_reject(source: str, row_ref: int, invoice_id: str, reason: str) -> None:
        rejects.append({"source": source, "row_ref": str(row_ref), "invoice_id": invoice_id, "reason": reason})

    api_rows = json.loads((input_dir / "api_invoices.json").read_text())
    for index, row in enumerate(api_rows, start=1):
        invoice_id = normalize_id(row.get("id"))
        status = normalize_status(row.get("state"))
        issued = parse_date(row.get("issued", ""))
        updated = parse_date(row.get("updated", ""))
        amount, amount_reason = cents(row.get("money", {}).get("value"), row.get("money", {}).get("currency"), rates)
        if not invoice_id:
            add_reject("api", index, invoice_id, "missing_invoice_id")
        elif status is None:
            add_reject("api", index, invoice_id, "unknown_status")
        elif issued is None or updated is None:
            add_reject("api", index, invoice_id, "malformed_date")
        elif amount is None:
            add_reject("api", index, invoice_id, amount_reason or "non_positive_amount")
        else:
            records.append(
                {
                    "invoice_id": invoice_id,
                    "customer": str(row.get("account", {}).get("name", "")).strip(),
                    "amount_usd_cents": amount,
                    "status": status,
                    "issued_at": issued,
                    "updated_at": updated,
                    "source": "api",
                    "row_ref": index,
                }
            )

    with (input_dir / "csv_invoices.csv").open(newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=1):
            invoice_id = normalize_id(row.get("invoice_id"))
            status = normalize_status(row.get("status"))
            issued = parse_date(row.get("issued_at", ""))
            updated = parse_date(row.get("updated_at", ""))
            amount, amount_reason = cents(row.get("amount"), row.get("currency"), rates)
            if not invoice_id:
                add_reject("csv", index, invoice_id, "missing_invoice_id")
            elif status is None:
                add_reject("csv", index, invoice_id, "unknown_status")
            elif issued is None or updated is None:
                add_reject("csv", index, invoice_id, "malformed_date")
            elif amount is None:
                add_reject("csv", index, invoice_id, amount_reason or "non_positive_amount")
            else:
                records.append(
                    {
                        "invoice_id": invoice_id,
                        "customer": str(row.get("customer", "")).strip(),
                        "amount_usd_cents": amount,
                        "status": status,
                        "issued_at": issued,
                        "updated_at": updated,
                        "source": "csv",
                        "row_ref": index,
                    }
                )

    for index, line in enumerate((input_dir / "legacy_invoices.txt").read_text().splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("|")
        invoice_id = normalize_id(parts[0] if len(parts) > 0 else "")
        status = normalize_status(parts[4] if len(parts) > 4 else "")
        issued = parse_date(parts[5] if len(parts) > 5 else "", legacy=True)
        updated = parse_date(parts[6] if len(parts) > 6 else "", legacy=True)
        amount, amount_reason = cents(parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else "", rates, legacy=True)
        if len(parts) != 7 or not invoice_id:
            add_reject("legacy", index, invoice_id, "missing_invoice_id")
        elif status is None:
            add_reject("legacy", index, invoice_id, "unknown_status")
        elif issued is None or updated is None:
            add_reject("legacy", index, invoice_id, "malformed_date")
        elif amount is None:
            add_reject("legacy", index, invoice_id, amount_reason or "non_positive_amount")
        else:
            records.append(
                {
                    "invoice_id": invoice_id,
                    "customer": parts[1].strip(),
                    "amount_usd_cents": amount,
                    "status": status,
                    "issued_at": issued,
                    "updated_at": updated,
                    "source": "legacy",
                    "row_ref": index,
                }
            )

    chosen: dict[str, dict[str, object]] = {}
    for row in records:
        existing = chosen.get(row["invoice_id"])
        if existing is None:
            chosen[row["invoice_id"]] = row
            continue
        current_key = (PRECEDENCE[row["source"]], row["updated_at"], row["row_ref"])
        existing_key = (PRECEDENCE[existing["source"]], existing["updated_at"], existing["row_ref"])
        if current_key > existing_key:
            chosen[row["invoice_id"]] = row

    merged = [
        {key: str(row[key]) for key in FIELDNAMES}
        for row in sorted(chosen.values(), key=lambda item: item["invoice_id"])
    ]
    rejects = sorted(rejects, key=lambda row: (SOURCE_ORDER[row["source"]], int(row["row_ref"])))
    summary = {
        "invoice_count": len(merged),
        "paid_total_usd_cents": sum(int(row["amount_usd_cents"]) for row in merged if row["status"] == "paid"),
        "open_total_usd_cents": sum(int(row["amount_usd_cents"]) for row in merged if row["status"] == "open"),
        "void_total_usd_cents": sum(int(row["amount_usd_cents"]) for row in merged if row["status"] == "void"),
        "rejected_count": len(rejects),
    }
    return merged, rejects, summary


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_cli(input_dir: Path, output_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "invoice_merge.cli",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_hidden_fixture(root: Path) -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    (input_dir / "currency_rates.json").write_text(json.dumps({"USD": "1", "EUR": "1.075", "CAD": "0.735"}, indent=2))
    write_csv(
        input_dir / "csv_invoices.csv",
        ["invoice_id", "customer", "amount", "currency", "status", "issued_at", "updated_at"],
        [
            {"invoice_id": "inv-501", "customer": "CSV Should Lose", "amount": "1.00", "currency": "USD", "status": "open", "issued_at": "2026-07-01", "updated_at": "2026-07-04"},
            {"invoice_id": "INV-502", "customer": "CSV Later", "amount": "10.01", "currency": "EUR", "status": "pending", "issued_at": "2026-07-02", "updated_at": "2026-07-06"},
            {"invoice_id": "INV-502", "customer": "CSV Earlier", "amount": "99.00", "currency": "USD", "status": "paid", "issued_at": "2026-07-02", "updated_at": "2026-07-05"},
            {"invoice_id": "INV-CSV-BAD", "customer": "Bad Status", "amount": "5.00", "currency": "USD", "status": "collecting", "issued_at": "2026-07-02", "updated_at": "2026-07-05"},
        ],
    )
    (input_dir / "api_invoices.json").write_text(
        json.dumps(
            [
                {"id": "INV-501", "account": {"name": "API Should Win"}, "money": {"value": "20.005", "currency": "CAD"}, "state": "settled", "issued": "2026-07-03", "updated": "2026-07-03"},
                {"id": "INV-503", "account": {"name": "API Void"}, "money": {"value": "7.00", "currency": "USD"}, "state": "cancelled", "issued": "2026-07-04", "updated": "2026-07-04"},
                {"id": "INV-API-BAD", "account": {"name": "Bad Date"}, "money": {"value": "4.00", "currency": "USD"}, "state": "paid", "issued": "07/04/2026", "updated": "2026-07-04"},
            ],
            indent=2,
        )
    )
    (input_dir / "legacy_invoices.txt").write_text(
        "\n".join(
            [
                "INV-504|Legacy Draft|3333|USD|draft|20260701|20260703",
                "INV-501|Legacy Loses|9999|USD|paid|20260701|20260710",
                "INV-LEG-BAD|Legacy Bad Currency|100|MXN|open|20260701|20260701",
            ]
        )
        + "\n"
    )
    return input_dir


class InvoiceMultiSourceMergeTests(unittest.TestCase):
    def assert_outputs(self, input_dir: Path, output_dir: Path) -> None:
        expected_merged, expected_rejected, expected_summary = expected(input_dir)
        self.assertEqual(read_csv(output_dir / "merged_invoices.csv"), expected_merged)
        self.assertEqual(read_csv(output_dir / "rejected_invoices.csv"), expected_rejected)
        self.assertEqual(json.loads((output_dir / "summary.json").read_text()), expected_summary)
        self.assertEqual(list(read_csv(output_dir / "merged_invoices.csv")[0]), FIELDNAMES)
        self.assertEqual(list(read_csv(output_dir / "rejected_invoices.csv")[0]), REJECT_FIELDNAMES)

    def test_visible_fixture_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            run_cli(Path("/app/input"), out)
            first = {name: (out / name).read_text() for name in ["merged_invoices.csv", "rejected_invoices.csv", "summary.json"]}
            run_cli(Path("/app/input"), out)
            second = {name: (out / name).read_text() for name in ["merged_invoices.csv", "rejected_invoices.csv", "summary.json"]}
            self.assertEqual(first, second)
            self.assert_outputs(Path("/app/input"), out)

    def test_hidden_fixture_exercises_precedence_rounding_and_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = write_hidden_fixture(Path(tmp))
            out = Path(tmp) / "out"
            run_cli(input_dir, out)
            self.assert_outputs(input_dir, out)

    def test_agent_added_multisource_regression_test(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = "/app"
        fixed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd="/app",
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)

        with tempfile.TemporaryDirectory() as tmp:
            mutant = Path(tmp) / "app"
            shutil.copytree("/app", mutant, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (mutant / "invoice_merge" / "importer.py").write_text(
                '''from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    customer: str
    amount_usd_cents: int
    status: str
    issued_at: str
    updated_at: str
    source: str


def import_invoices(input_dir: str | Path):
    invoices = []
    with (Path(input_dir) / "csv_invoices.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            invoices.append(Invoice(row["invoice_id"].strip().upper(), row["customer"].strip(), int(float(row["amount"]) * 100), row["status"].strip().lower(), row["issued_at"], row["updated_at"], "csv"))
    return invoices, []
'''
            )
            env["PYTHONPATH"] = str(mutant)
            mutant_result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=mutant,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        self.assertNotEqual(mutant_result.returncode, 0, "visible tests did not catch a CSV-only importer")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InvoiceMultiSourceMergeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"

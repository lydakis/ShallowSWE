#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import json
import subprocess
import sys
import tempfile
import unittest


def write_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "accounts.csv").write_text(
        "account_id,status,plan_id\n"
        "acct_1,active,basic\n"
        "acct_2,active,pro\n"
        "acct_3,suspended,basic\n"
    )
    (root / "plans.json").write_text(
        json.dumps(
            [
                {"plan_id": "basic", "currency": "USD", "unit_price_cents": 10},
                {"plan_id": "pro", "currency": "USD", "unit_price_cents": 25},
            ]
        )
        + "\n"
    )
    usage_rows = [
        {
            "version": 1,
            "usage_id": "u1",
            "account_id": "acct_1",
            "units": 3,
            "occurred_at": "2026-01-01T00:00:00Z",
        },
        {
            "version": 2,
            "usage_id": "u2",
            "account_id": "acct_2",
            "plan_id": "pro",
            "units": 2,
            "occurred_at": "2026-01-01T01:00:00Z",
            "source": "api",
        },
        {
            "version": 2,
            "usage_id": "u3",
            "account_id": "acct_1",
            "plan_id": "pro",
            "units": 1,
            "occurred_at": "2026-01-01T02:00:00Z",
            "source": "meter",
        },
        {
            "version": 1,
            "usage_id": "u_dup",
            "account_id": "acct_1",
            "units": 1,
            "occurred_at": "2026-01-01T03:00:00Z",
        },
        {
            "version": 1,
            "usage_id": "u_dup",
            "account_id": "acct_1",
            "units": 5,
            "occurred_at": "2026-01-01T03:05:00Z",
        },
        {
            "version": 1,
            "usage_id": "u_unknown_account",
            "account_id": "acct_missing",
            "units": 1,
            "occurred_at": "2026-01-01T04:00:00Z",
        },
        {
            "version": 2,
            "usage_id": "u_unknown_plan",
            "account_id": "acct_1",
            "plan_id": "missing",
            "units": 1,
            "occurred_at": "2026-01-01T05:00:00Z",
            "source": "meter",
        },
        {
            "version": 1,
            "usage_id": "u_invalid_units",
            "account_id": "acct_1",
            "units": 0,
            "occurred_at": "2026-01-01T06:00:00Z",
        },
        {
            "version": 1,
            "usage_id": "u_suspended",
            "account_id": "acct_3",
            "units": 2,
            "occurred_at": "2026-01-01T07:00:00Z",
        },
    ]
    (root / "usage.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in usage_rows)
    )
    (root / "credits.csv").write_text(
        "credit_id,account_id,amount_cents\n"
        "c1,acct_1,50\n"
        "c2,acct_2,20\n"
        "c_unknown,acct_missing,99\n"
    )
    (root / "legacy_adjustments.csv").write_text(
        "adjustment_id,account_id,amount_cents,reason\n"
        "a1,acct_1,-10,outage\n"
        "a2,acct_2,15,late_fee\n"
        "a_unknown,acct_missing,10,manual\n"
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


class HiddenLedgerSchemaUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        write_fixture(self.input_dir)
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
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_output_schemas_are_exact(self) -> None:
        normalized = [
            json.loads(line)
            for line in (self.output_dir / "normalized_events.jsonl").read_text().splitlines()
        ]
        ledger = read_csv(self.output_dir / "ledger.csv")
        rejects = read_csv(self.output_dir / "rejects.csv")

        self.assertEqual(
            set(normalized[0]),
            {
                "event_id",
                "account_id",
                "plan_id",
                "units",
                "currency",
                "gross_cents",
                "source",
                "occurred_at",
            },
        )
        self.assertEqual(
            list(ledger[0]),
            ["account_id", "event_id", "event_type", "amount_cents", "running_balance_cents"],
        )
        self.assertEqual(list(rejects[0]), ["input", "event_id", "reason"])

    def test_normalized_events_are_canonical(self) -> None:
        normalized = [
            json.loads(line)
            for line in (self.output_dir / "normalized_events.jsonl").read_text().splitlines()
        ]

        self.assertEqual(
            normalized,
            [
                {
                    "event_id": "u1",
                    "account_id": "acct_1",
                    "plan_id": "basic",
                    "units": 3,
                    "currency": "USD",
                    "gross_cents": 30,
                    "source": "legacy",
                    "occurred_at": "2026-01-01T00:00:00Z",
                },
                {
                    "event_id": "u2",
                    "account_id": "acct_2",
                    "plan_id": "pro",
                    "units": 2,
                    "currency": "USD",
                    "gross_cents": 50,
                    "source": "api",
                    "occurred_at": "2026-01-01T01:00:00Z",
                },
                {
                    "event_id": "u3",
                    "account_id": "acct_1",
                    "plan_id": "pro",
                    "units": 1,
                    "currency": "USD",
                    "gross_cents": 25,
                    "source": "meter",
                    "occurred_at": "2026-01-01T02:00:00Z",
                },
                {
                    "event_id": "u_dup",
                    "account_id": "acct_1",
                    "plan_id": "basic",
                    "units": 1,
                    "currency": "USD",
                    "gross_cents": 10,
                    "source": "legacy",
                    "occurred_at": "2026-01-01T03:00:00Z",
                },
            ],
        )

    def test_ledger_applies_adjustments_then_capped_credits_per_account(self) -> None:
        ledger = read_csv(self.output_dir / "ledger.csv")

        self.assertEqual(
            ledger,
            [
                {
                    "account_id": "acct_1",
                    "event_id": "u1",
                    "event_type": "usage",
                    "amount_cents": "30",
                    "running_balance_cents": "30",
                },
                {
                    "account_id": "acct_1",
                    "event_id": "u3",
                    "event_type": "usage",
                    "amount_cents": "25",
                    "running_balance_cents": "55",
                },
                {
                    "account_id": "acct_1",
                    "event_id": "u_dup",
                    "event_type": "usage",
                    "amount_cents": "10",
                    "running_balance_cents": "65",
                },
                {
                    "account_id": "acct_1",
                    "event_id": "a1",
                    "event_type": "adjustment",
                    "amount_cents": "-10",
                    "running_balance_cents": "55",
                },
                {
                    "account_id": "acct_1",
                    "event_id": "c1",
                    "event_type": "credit",
                    "amount_cents": "-50",
                    "running_balance_cents": "5",
                },
                {
                    "account_id": "acct_2",
                    "event_id": "u2",
                    "event_type": "usage",
                    "amount_cents": "50",
                    "running_balance_cents": "50",
                },
                {
                    "account_id": "acct_2",
                    "event_id": "a2",
                    "event_type": "adjustment",
                    "amount_cents": "15",
                    "running_balance_cents": "65",
                },
                {
                    "account_id": "acct_2",
                    "event_id": "c2",
                    "event_type": "credit",
                    "amount_cents": "-20",
                    "running_balance_cents": "45",
                },
            ],
        )

    def test_rejects_have_distinct_reasons(self) -> None:
        rejects = read_csv(self.output_dir / "rejects.csv")

        self.assertEqual(
            rejects,
            [
                {"input": "adjustment", "event_id": "a_unknown", "reason": "UNKNOWN_ACCOUNT"},
                {"input": "credit", "event_id": "c_unknown", "reason": "UNKNOWN_ACCOUNT"},
                {"input": "usage", "event_id": "u_dup", "reason": "DUPLICATE_USAGE_ID"},
                {"input": "usage", "event_id": "u_invalid_units", "reason": "INVALID_UNITS"},
                {"input": "usage", "event_id": "u_suspended", "reason": "SUSPENDED_ACCOUNT"},
                {"input": "usage", "event_id": "u_unknown_account", "reason": "UNKNOWN_ACCOUNT"},
                {"input": "usage", "event_id": "u_unknown_plan", "reason": "UNKNOWN_PLAN"},
            ],
        )

    def test_summary_totals_match_ledger(self) -> None:
        summary = json.loads((self.output_dir / "summary.json").read_text())

        self.assertEqual(
            summary,
            {
                "usage_events": 4,
                "adjustment_events": 2,
                "credit_events": 2,
                "reject_count": 7,
                "gross_cents": 115,
                "adjustment_cents": 5,
                "credit_cents": -70,
                "net_cents": 50,
            },
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenLedgerSchemaUpgradeTests)
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

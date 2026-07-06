#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "/app")

from dispatch_app.config import DispatchConfig
from dispatch_app.orders import Order, load_orders
from dispatch_app.planner import plan_dispatch


APP = Path("/app")


def hidden_orders() -> list[Order]:
    rows = [
        {
            "id": "DSP-900",
            "region": "north",
            "account": "initech",
            "state": "active",
            "ready": True,
            "priority": 1,
            "promised_at": "2026-07-07T09:00:00Z",
            "destination_zone": "N1",
        },
        {
            "id": "DSP-999",
            "region": "north",
            "account": "initech",
            "state": "active",
            "ready": True,
            "priority": 9,
            "promised_at": "2026-07-07T10:00:00Z",
            "destination_zone": "N1",
        },
        {
            "id": "DSP-901",
            "region": "north",
            "account": "initech",
            "state": "active",
            "ready": True,
            "priority": 2,
            "promised_at": "2026-07-07T10:00:00Z",
            "destination_zone": "N1",
        },
        {
            "id": "DSP-902",
            "region": "north",
            "account": "initech",
            "state": "active",
            "ready": True,
            "priority": 2,
            "promised_at": "2026-07-07T10:00:00Z",
            "destination_zone": "N2",
        },
        {
            "id": "DSP-903",
            "region": "north",
            "account": "initech",
            "state": "archived",
            "ready": True,
            "priority": 8,
            "promised_at": "2026-07-07T08:00:00Z",
            "destination_zone": "N1",
        },
        {
            "id": "DSP-904",
            "region": "north",
            "account": "initech",
            "state": "blocked",
            "ready": True,
            "priority": 10,
            "promised_at": "2026-07-07T07:00:00Z",
            "destination_zone": "N1",
        },
        {
            "id": "DSP-905",
            "region": "south",
            "account": "initech",
            "state": "active",
            "ready": True,
            "priority": 10,
            "promised_at": "2026-07-07T06:00:00Z",
            "destination_zone": "S1",
        },
        {
            "id": "DSP-906",
            "region": "north",
            "account": "initech",
            "state": "active",
            "ready": False,
            "priority": 10,
            "promised_at": "2026-07-07T05:00:00Z",
            "destination_zone": "N1",
        },
    ]
    return [Order(**row) for row in rows]


class DispatchPlannerSplitParityTests(unittest.TestCase):
    def test_required_pipeline_layout_exists(self) -> None:
        required = [
            APP / "dispatch_app/pipeline/__init__.py",
            APP / "dispatch_app/pipeline/filters.py",
            APP / "dispatch_app/pipeline/ordering.py",
            APP / "dispatch_app/pipeline/planner.py",
        ]

        for path in required:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"missing {path.relative_to(APP)}")

    def test_public_planner_is_thin_compatibility_wrapper(self) -> None:
        text = (APP / "dispatch_app/planner.py").read_text()

        self.assertIn(".pipeline", text)
        self.assertNotIn("Known bug", text)
        self.assertLessEqual(text.count("for "), 1)

    def test_visible_corpus_preserves_existing_filters_and_fixes_priority_tie(self) -> None:
        orders = load_orders(APP / "orders.json")

        self.assertEqual(
            plan_dispatch(
                orders,
                DispatchConfig(region="west", account="acme", include_archived=False),
            ),
            ["DSP-100", "DSP-101", "DSP-120", "DSP-110"],
        )
        self.assertEqual(
            plan_dispatch(
                orders,
                DispatchConfig(region="west", account="acme", include_archived=True),
            ),
            ["DSP-100", "DSP-102", "DSP-101", "DSP-120", "DSP-110"],
        )

    def test_hidden_corpus_applies_all_filters_and_priority_tiebreak(self) -> None:
        orders = hidden_orders()

        self.assertEqual(
            plan_dispatch(
                orders,
                DispatchConfig(region="north", account="initech", include_archived=False),
            ),
            ["DSP-900", "DSP-999", "DSP-901", "DSP-902"],
        )
        self.assertEqual(
            plan_dispatch(
                orders,
                DispatchConfig(region="north", account="initech", include_archived=True),
            ),
            ["DSP-903", "DSP-900", "DSP-999", "DSP-901", "DSP-902"],
        )

    def test_cli_output_contract_is_unchanged(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(
                "DISPATCH_REGION=west\n"
                "DISPATCH_ACCOUNT=acme\n"
                "DISPATCH_INCLUDE_ARCHIVED=1\n"
            )
            env_file = Path(handle.name)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dispatch_app.cli",
                "--orders",
                str(APP / "orders.json"),
                "--env-file",
                str(env_file),
            ],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["DSP-100", "DSP-102", "DSP-101", "DSP-120", "DSP-110"],
        )

    def test_pipeline_handles_json_loaded_hidden_orders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.json"
            path.write_text(json.dumps([order.__dict__ for order in hidden_orders()]))
            loaded = load_orders(path)

        self.assertEqual(
            plan_dispatch(
                loaded,
                DispatchConfig(region="north", account="initech", include_archived=False),
            ),
            ["DSP-900", "DSP-999", "DSP-901", "DSP-902"],
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DispatchPlannerSplitParityTests)
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

#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "/app")

from dispatch_app.config import load_config
from dispatch_app.orders import load_orders
from dispatch_app.planner import plan_dispatch


class HiddenConfigFlagTests(unittest.TestCase):
    def test_documented_include_archived_flag_is_loaded(self) -> None:
        config = load_config("/app/.env.nightly")

        self.assertEqual(config.region, "west")
        self.assertTrue(config.include_archived)

    def test_documented_flag_changes_dispatch_plan(self) -> None:
        plan = plan_dispatch(load_orders("/app/orders.json"), load_config("/app/.env.nightly"))

        self.assertEqual(plan, ["ORD-100", "ORD-101"])

    def test_cli_reads_documented_flag(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dispatch_app.cli",
                "--orders",
                "/app/orders.json",
                "--env-file",
                "/app/.env.nightly",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertEqual(result.stdout.splitlines(), ["ORD-100", "ORD-101"])

    def test_legacy_alias_still_works(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("DISPATCH_REGION=west\n")
            handle.write("DISPATCH_INCLUDE_CLOSED=1\n")
            env_file = Path(handle.name)

        config = load_config(env_file)

        self.assertTrue(config.include_archived)

    def test_archived_orders_still_skipped_by_default(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("DISPATCH_REGION=west\n")
            env_file = Path(handle.name)

        plan = plan_dispatch(load_orders("/app/orders.json"), load_config(env_file))

        self.assertEqual(plan, ["ORD-100"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenConfigFlagTests)
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

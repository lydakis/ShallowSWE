#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

app = Path(os.environ.get("APP_DIR", "/app"))
sys.path.insert(0, str(app))

from dispatch_app.config import load_config
from dispatch_app.orders import load_orders
from dispatch_app.planner import plan_dispatch


class HiddenConfigFlagTests(unittest.TestCase):
    def test_documented_include_archived_flag_is_loaded(self) -> None:
        config = load_config(app / ".env.nightly")

        self.assertEqual(config.region, "west")
        self.assertTrue(config.include_archived)

    def test_documented_flag_works_in_arbitrary_env_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("DISPATCH_REGION=west\n")
            handle.write("DISPATCH_INCLUDE_ARCHIVED=1\n")
            env_file = Path(handle.name)

        self.assertTrue(load_config(env_file).include_archived)

    def test_documented_flag_works_from_process_environment(self) -> None:
        with patch.dict(
            os.environ,
            {"DISPATCH_INCLUDE_ARCHIVED": "1"},
            clear=True,
        ):
            self.assertTrue(load_config().include_archived)

    def test_documented_flag_changes_dispatch_plan(self) -> None:
        plan = plan_dispatch(load_orders(app / "orders.json"), load_config(app / ".env.nightly"))

        self.assertEqual(plan, ["ORD-100", "ORD-101"])

    def test_cli_reads_documented_flag(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(app)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dispatch_app.cli",
                "--orders",
                str(app / "orders.json"),
                "--env-file",
                str(app / ".env.nightly"),
            ],
            check=True,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertEqual(result.stdout.splitlines(), ["ORD-100", "ORD-101"])

    def test_cli_command_name_is_stable(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(app)
        result = subprocess.run(
            [sys.executable, "-m", "dispatch_app.cli", "--help"],
            check=True,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
        )

        self.assertTrue(result.stdout.startswith("usage: dispatch-plan"))

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

        plan = plan_dispatch(load_orders(app / "orders.json"), load_config(env_file))

        self.assertEqual(plan, ["ORD-100"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenConfigFlagTests)
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

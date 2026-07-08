#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "/app")

from dispatch_app.config import load_config
from dispatch_app.orders import load_orders
from dispatch_app.planner import plan_dispatch


ORDERS = "/app/orders.json"


def write_env(text: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", delete=False)
    with handle:
        handle.write(text)
    return Path(handle.name)


def plan_for(text: str) -> list[str]:
    return plan_dispatch(load_orders(ORDERS), load_config(write_env(text)))


class HiddenConfigKeyRolloverTests(unittest.TestCase):
    def test_committed_env_fixtures_use_new_key(self) -> None:
        expected = {
            ".env.nightly": "DISPATCH_VISIBILITY=all",
            ".env.legacy": "DISPATCH_VISIBILITY=all",
            ".env.preview": "DISPATCH_VISIBILITY=all",
            ".env.backfill": "DISPATCH_VISIBILITY=all",
        }
        for name, visibility_line in expected.items():
            with self.subTest(name=name):
                text = Path(f"/app/{name}").read_text()
                self.assertIn(visibility_line, text)
                self.assertNotIn("DISPATCH_INCLUDE_CLOSED", text)

    def test_migrated_env_fixtures_still_drive_expected_plans(self) -> None:
        cases = {
            ".env.nightly": ["DSP-100", "DSP-101"],
            ".env.legacy": ["DSP-100", "DSP-101"],
            ".env.preview": ["DSP-104"],
            ".env.backfill": ["DSP-103"],
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                plan = plan_dispatch(load_orders(ORDERS), load_config(Path(f"/app/{name}")))
                self.assertEqual(plan, expected)

    def test_default_and_explicit_active_visibility(self) -> None:
        default_plan = plan_for("DISPATCH_REGION=west\nDISPATCH_ACCOUNT=acme\n")
        active_plan = plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_VISIBILITY=active\n"
        )

        self.assertEqual(default_plan, ["DSP-100"])
        self.assertEqual(active_plan, ["DSP-100"])

    def test_archived_visibility_only_includes_archived_ready_orders(self) -> None:
        plan = plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_VISIBILITY=archived\n"
        )

        self.assertEqual(plan, ["DSP-101"])

    def test_all_visibility_includes_active_and_archived_orders(self) -> None:
        plan = plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_VISIBILITY=all\n"
        )

        self.assertEqual(plan, ["DSP-100", "DSP-101"])

    def test_legacy_alias_maps_to_all_when_new_key_absent(self) -> None:
        plan = plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_INCLUDE_CLOSED=1\n"
        )

        self.assertEqual(plan, ["DSP-100", "DSP-101"])

    def test_new_key_wins_when_both_keys_are_present(self) -> None:
        active_plan = plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_INCLUDE_CLOSED=1\n"
            "DISPATCH_VISIBILITY=active\n"
        )
        archived_plan = plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_INCLUDE_CLOSED=0\n"
            "DISPATCH_VISIBILITY=archived\n"
        )

        self.assertEqual(active_plan, ["DSP-100"])
        self.assertEqual(archived_plan, ["DSP-101"])

    def test_existing_region_and_account_filters_still_work(self) -> None:
        east_plan = plan_for(
            "DISPATCH_REGION=east\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_VISIBILITY=all\n"
        )
        account_plan = plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=globex\n"
            "DISPATCH_VISIBILITY=all\n"
        )

        self.assertEqual(east_plan, ["DSP-104"])
        self.assertEqual(account_plan, ["DSP-103"])

    def test_cli_keeps_command_behavior_and_output_format(self) -> None:
        env_file = write_env(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_VISIBILITY=all\n"
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dispatch_app.cli",
                "--orders",
                ORDERS,
                "--env-file",
                str(env_file),
            ],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.stdout.splitlines(), ["DSP-100", "DSP-101"])

    def test_cli_help_and_readme_name_new_public_contract(self) -> None:
        help_result = subprocess.run(
            [sys.executable, "-m", "dispatch_app.cli", "--help"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        readme = Path("/app/README.md").read_text()

        for text in (help_result.stdout, readme):
            self.assertIn("DISPATCH_VISIBILITY", text)
            self.assertIn("active", text)
            self.assertIn("archived", text)
            self.assertIn("all", text)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HiddenConfigKeyRolloverTests)
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

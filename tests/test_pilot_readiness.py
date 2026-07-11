from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from shallowswe.cli import main
from shallowswe.pilot_readiness import audit_pilot_readiness


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "configs" / "shallowswe-six-task-pilot-v0.3.json"


class PilotReadinessTests(unittest.TestCase):
    def test_manifest_freezes_revised_allocation_and_censoring_boundaries(self) -> None:
        report = audit_pilot_readiness(MANIFEST, repo_root=REPO_ROOT)

        self.assertTrue(report["structurally_valid"])
        self.assertFalse(report["ready_for_official_canary"])
        self.assertEqual(report["task_count"], 6)
        self.assertEqual(report["categories"], {"artifact": 2, "code": 2, "workflow": 2})
        self.assertEqual(
            report["confirmation_task_ids"],
            [
                "access-log-to-incidents",
                "invoice-multi-source-merge",
                "merge-divergent-config-branches",
            ],
        )
        self.assertEqual(report["stage_totals"]["permissive_collection"], 72)
        self.assertNotIn("one_shot_measurement", report["stage_totals"])
        self.assertEqual(report["official_core_trajectories"], 112)
        self.assertNotIn("model_config_not_frozen", report["blockers"])
        self.assertNotIn("model_config_canonical_json_incomplete", report["blockers"])
        self.assertNotIn("agent_policy_not_frozen", report["blockers"])
        self.assertEqual(len(report["model_config_ids"]), 3)
        self.assertEqual(len(report["agent_policy_ids"]), 3)
        self.assertNotIn("pilot_task_quality_incomplete", report["blockers"])
        self.assertEqual(len(report["quality_ready_tasks"]), 6)
        self.assertIn("pilot_routine_review_incomplete", report["blockers"])
        self.assertTrue(report["pilot_schedule"]["valid"])
        self.assertEqual(report["pilot_schedule"]["trajectory_count"], 178)
        self.assertTrue(report["pilot_launch_plan"]["valid"])
        self.assertEqual(report["pilot_launch_plan"]["launch_unit_count"], 14)
        self.assertEqual(report["budget_preflight"]["core_high_estimate_usd"], 63.0)
        self.assertEqual(report["budget_preflight"]["headroom_usd"], 137.0)

    def test_cli_emits_readiness_report(self) -> None:
        output = StringIO()
        with (
            patch("sys.argv", ["shallowswe", "pilot-readiness", str(MANIFEST)]),
            redirect_stdout(output),
        ):
            main()

        report = json.loads(output.getvalue())
        self.assertEqual(report["manifest"], "shallowswe-six-task-pilot-v0.3")
        self.assertEqual(report["methodology_version"], "v0.4.2")

    def test_rejects_confirmation_set_without_one_task_per_category(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        manifest["confirmation_task_ids"] = [
            "invoice-cli-regression-test-fix",
            "invoice-multi-source-merge",
            "merge-divergent-config-branches",
        ]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest))

            report = audit_pilot_readiness(path, repo_root=REPO_ROOT)

        self.assertIn("invalid_confirmation_task_ids", report["issues"])

    def test_rejects_standalone_one_shot_measurement_policy(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        manifest["pilot_measurement_policy"]["standalone_one_shot_stage"] = True
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest))

            report = audit_pilot_readiness(path, repo_root=REPO_ROOT)

        self.assertIn(
            "invalid_pilot_measurement_policy:standalone_one_shot_stage",
            report["issues"],
        )


if __name__ == "__main__":
    unittest.main()

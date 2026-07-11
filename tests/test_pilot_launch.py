from __future__ import annotations

from pathlib import Path
import unittest

from shallowswe.pilot_launch import build_pilot_launch_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "configs" / "shallowswe-six-task-pilot-v0.3.json"
SCHEDULE = REPO_ROOT / "configs" / "shallowswe-six-task-pilot-v0.3-schedule.json"


class PilotLaunchPlanTests(unittest.TestCase):
    def test_groups_reserved_rows_into_budget_gated_launch_units(self) -> None:
        plan = build_pilot_launch_plan(MANIFEST, SCHEDULE)

        self.assertEqual(plan["trajectory_count"], 178)
        self.assertEqual(plan["official_trajectory_count"], 112)
        self.assertEqual(plan["launch_unit_count"], 14)
        anchor = next(
            unit
            for unit in plan["units"]
            if unit["stage"] == "permissive_collection"
            and unit["model_role"] == "primary_anchor"
        )
        self.assertEqual(anchor["expected_trajectories"], 36)
        self.assertEqual(anchor["policy"]["verifier_submission_cap"], 16)
        self.assertEqual(anchor["launch_status"], "blocked_by_pilot_readiness")
        confirmation = next(
            unit for unit in plan["units"] if unit["stage"] == "fresh_anchor_confirmation"
        )
        self.assertIsNone(confirmation["policy"]["verifier_submission_cap"])
        self.assertEqual(confirmation["launch_status"], "blocked_by_stage4_policy_freeze")
        self.assertEqual(
            confirmation["task_ids"],
            [
                "access-log-to-incidents",
                "invoice-multi-source-merge",
                "merge-divergent-config-branches",
            ],
        )


if __name__ == "__main__":
    unittest.main()

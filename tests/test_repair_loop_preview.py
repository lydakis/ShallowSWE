from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import json
import unittest

from shallowswe.cli import main
from shallowswe.repair_loop_preview import audit_repair_loop_preview_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "configs" / "shallowswe-repair-loop-preview-n3-18.json"


class RepairLoopPreviewPlanTests(unittest.TestCase):
    def test_preview_plan_is_budget_guarded_and_ready_to_launch(self) -> None:
        report = audit_repair_loop_preview_plan(PLAN_PATH, repo_root=REPO_ROOT)

        self.assertEqual(
            report["schema_version"],
            "shallowswe.repair_loop_preview_plan_audit.v0.1",
        )
        self.assertTrue(report["valid"])
        self.assertTrue(report["ready_to_launch"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["task_count"], 18)
        self.assertEqual(report["model_rows"], 10)
        self.assertEqual(report["repair_loop_seeds_per_task_model_config"], 3)
        self.assertEqual(report["estimated_total_rows"], 540)
        self.assertEqual(set(report["cell_counts"].values()), {2})
        self.assertEqual(report["verifier_submission_cap"], 20)
        self.assertEqual(report["agent_step_cap"], 120)
        self.assertEqual(report["per_row_dollar_cap_usd"], 5.0)
        self.assertEqual(report["global_hard_stop_usd"], 250.0)
        self.assertEqual(report["budget_limit_usd"], 250.0)
        self.assertLess(
            report["budget_estimates"]["conservative_existing_guard"],
            report["global_hard_stop_usd"],
        )

    def test_preview_plan_cli_reports_hard_stop(self) -> None:
        output = StringIO()
        with (
            patch("sys.argv", ["shallowswe", "repair-loop-preview-plan", str(PLAN_PATH)]),
            redirect_stdout(output),
        ):
            main()

        report = json.loads(output.getvalue())

        self.assertTrue(report["ready_to_launch"])
        self.assertEqual(report["global_hard_stop_usd"], 250.0)
        self.assertEqual(report["estimated_total_rows"], 540)


if __name__ == "__main__":
    unittest.main()

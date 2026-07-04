from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import json
import unittest

from shallowswe.calibration_plan import audit_calibration_plan
from shallowswe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "configs" / "shallowswe-v1-calibration-plan.json"


class CalibrationPlanTests(unittest.TestCase):
    def test_v1_calibration_plan_is_valid_and_budget_gated(self) -> None:
        report = audit_calibration_plan(PLAN_PATH, repo_root=REPO_ROOT)
        groups = {group["id"]: group for group in report["run_groups"]}

        self.assertEqual(report["schema_version"], "shallowswe.calibration_plan_audit.v0.1")
        self.assertTrue(report["valid"])
        self.assertFalse(report["ready_to_run_without_budget_override"])
        self.assertEqual(report["official_task_count"], 36)
        self.assertEqual(report["run_group_issue_counts"], {})
        self.assertEqual(
            report["budget_status_counts"],
            {"approval_required": 1, "within_budget": 1},
        )

        ceiling = groups["ceiling-admission-primary-n16"]
        self.assertEqual(ceiling["planned_attempts"], 36 * 16)
        self.assertEqual(ceiling["current_rollouts_per_task_min"], 1)
        self.assertEqual(ceiling["tasks_below_target"], 36)
        self.assertEqual(ceiling["budget_status"], "approval_required")
        self.assertTrue(ceiling["requires_explicit_approval"])
        self.assertIs(ceiling["panel_allows_fallbacks"], False)

        floor = groups["floor-size-calibration-panel-n10"]
        self.assertEqual(floor["planned_attempts"], 36 * 3 * 10)
        self.assertEqual(floor["current_rollouts_per_task_min"], 1)
        self.assertEqual(floor["tasks_below_target"], 36)
        self.assertEqual(floor["budget_status"], "within_budget")
        self.assertFalse(floor["requires_explicit_approval"])
        self.assertIs(floor["panel_allows_fallbacks"], False)

    def test_calibration_plan_cli_reports_audit(self) -> None:
        output = StringIO()
        with (
            patch("sys.argv", ["shallowswe", "calibration-plan", str(PLAN_PATH)]),
            redirect_stdout(output),
        ):
            main()

        report = json.loads(output.getvalue())

        self.assertEqual(report["plan"], "shallowswe-v1-calibration-plan")
        self.assertTrue(report["valid"])
        self.assertFalse(report["ready_to_run_without_budget_override"])


if __name__ == "__main__":
    unittest.main()

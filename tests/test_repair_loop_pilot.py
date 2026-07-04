from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import json
import unittest

from shallowswe.cli import main
from shallowswe.repair_loop_pilot import audit_repair_loop_pilot_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "configs" / "shallowswe-repair-loop-pilot-v0.1.json"


class RepairLoopPilotPlanTests(unittest.TestCase):
    def test_pilot_plan_is_valid_and_ready_with_resumable_agent(self) -> None:
        report = audit_repair_loop_pilot_plan(PLAN_PATH, repo_root=REPO_ROOT)

        self.assertEqual(
            report["schema_version"],
            "shallowswe.repair_loop_pilot_plan_audit.v0.1",
        )
        self.assertTrue(report["valid"])
        self.assertTrue(report["ready_for_final_protocol_pilot"])
        self.assertTrue(report["can_run_protocol_smoke"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["task_count"], 6)
        self.assertEqual(
            report["categories"],
            {"artifact": 2, "code": 2, "workflow": 2},
        )
        self.assertEqual(
            report["sizes"],
            {"large": 2, "medium": 2, "small": 2},
        )
        self.assertEqual(
            report["final_protocol_eligible_model_configs"],
            ["resumable_mini_swe_gemini_3_5_flash_medium"],
        )
        self.assertEqual(
            report["non_eligible_model_configs"],
            ["local_oracle_protocol_smoke"],
        )

    def test_pilot_plan_records_mini_swe_fork_capabilities(self) -> None:
        report = audit_repair_loop_pilot_plan(PLAN_PATH, repo_root=REPO_ROOT)

        self.assertTrue(report["fork_required"])
        self.assertTrue(report["fork_satisfied"])
        self.assertEqual(report["fork_missing_capabilities"], [])
        self.assertEqual(
            sorted(report["allowed_feedback_classes"]),
            [
                "generic_failure",
                "missing_required_artifact",
                "output_mismatch",
                "runtime_error",
            ],
        )

    def test_repair_loop_pilot_plan_cli_reports_capability_gate(self) -> None:
        output = StringIO()
        with (
            patch("sys.argv", ["shallowswe", "repair-loop-pilot-plan", str(PLAN_PATH)]),
            redirect_stdout(output),
        ):
            main()

        report = json.loads(output.getvalue())

        self.assertEqual(report["plan"], "shallowswe-repair-loop-pilot-v0.1")
        self.assertTrue(report["valid"])
        self.assertTrue(report["ready_for_final_protocol_pilot"])
        self.assertEqual(report["blockers"], [])


if __name__ == "__main__":
    unittest.main()

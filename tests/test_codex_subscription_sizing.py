from __future__ import annotations

import unittest

from scripts.run_codex_subscription_sizing import build_report


class CodexSubscriptionSizingTests(unittest.TestCase):
    def test_high_effort_diagnostic_does_not_count_as_fixed_ceiling(self) -> None:
        report = build_report(
            task_metadata=[
                {
                    "task_id": "example-task",
                    "category": "code",
                    "size": "medium",
                    "calibration_status": "candidate",
                }
            ],
            ceiling_rows_by_effort={
                "medium": [{"task_id": "example-task", "passed": False}],
                "high": [{"task_id": "example-task", "passed": True}],
            },
            floor_rows=[
                {"task_id": "example-task", "passed": True},
                {"task_id": "example-task", "passed": False},
                {"task_id": "example-task", "passed": False},
            ],
            status={
                "stages": {
                    "floor_gpt54mini_low": {
                        "attempts_per_task": 3,
                    }
                }
            },
        )

        task = report["tasks"][0]

        self.assertFalse(task["codex_5_5_medium_ceiling"]["passed"])
        self.assertTrue(task["codex_5_5_diagnostics"]["high"]["passed"])
        self.assertEqual(task["codex_5_5_diagnostic_rescue_effort"], "high")
        self.assertEqual(task["provisional_floor_size"], "medium")


if __name__ == "__main__":
    unittest.main()

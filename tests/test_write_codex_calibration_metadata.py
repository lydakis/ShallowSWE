from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.write_codex_calibration_metadata import (
    calibration_row_from_task,
    format_marker,
    write_markdown,
)


class WriteCodexCalibrationMetadataTests(unittest.TestCase):
    def test_medium_gpt55_report_is_written_as_smoke_not_ceiling(self) -> None:
        row = calibration_row_from_task(
            {
                "task_id": "example-task",
                "category": "workflow",
                "metadata_size": "large",
                "provisional_floor_size": "medium",
                "codex_5_5_formal_ceiling_effort": "medium",
                "codex_5_5_formal_ceiling": {
                    "attempts": 1,
                    "passes": 1,
                    "pass_rate": 1.0,
                },
                "codex_5_4_mini_low_attempts": 3,
                "codex_5_4_mini_low_passes": 1,
                "codex_5_4_mini_low_pass_rate": 1 / 3,
            },
            contract_review="no_failed_trajectory",
            contract_issue=False,
            failed_trajectory_count=0,
            report_path=Path("results/report.json"),
            audit_path=Path("results/audit.json"),
        )

        marker = format_marker(row, "calibration.codex_subscription_test")

        self.assertEqual(row["calibration_status"], "triaged_medium_smoke_only")
        self.assertIn('medium_smoke_model_config = "openai/gpt-5.5[medium]"', marker)
        self.assertIn('ceiling_model_config = "openai/gpt-5.5[extra_high]"', marker)
        self.assertIn("ceiling_attempts = 0", marker)
        self.assertNotIn('ceiling_model_config = "openai/gpt-5.5[medium]"', marker)

    def test_extra_high_report_is_written_as_ceiling(self) -> None:
        row = calibration_row_from_task(
            {
                "task_id": "example-task",
                "category": "workflow",
                "metadata_size": "large",
                "provisional_floor_size": "large",
                "codex_5_5_formal_ceiling_effort": "xhigh",
                "codex_5_5_formal_ceiling": {
                    "attempts": 1,
                    "passes": 1,
                    "pass_rate": 1.0,
                },
                "codex_5_5_medium_smoke": {
                    "attempts": 1,
                    "passes": 1,
                    "pass_rate": 1.0,
                },
                "codex_5_4_mini_low_attempts": 3,
                "codex_5_4_mini_low_passes": 0,
                "codex_5_4_mini_low_pass_rate": 0.0,
            },
            contract_review="no_failed_trajectory",
            contract_issue=False,
            failed_trajectory_count=0,
            report_path=Path("results/report.json"),
            audit_path=Path("results/audit.json"),
        )

        marker = format_marker(row, "calibration.codex_subscription_test")

        self.assertEqual(row["calibration_status"], "calibrated_provisional")
        self.assertIn('medium_smoke_model_config = "openai/gpt-5.5[medium]"', marker)
        self.assertIn('ceiling_model_config = "openai/gpt-5.5[extra_high]"', marker)
        self.assertIn("ceiling_attempts = 1", marker)

    def test_markdown_separates_extra_high_ceiling_from_medium_smoke(self) -> None:
        manifest = {
            "task_count": 1,
            "summary": {
                "assigned_size_counts": {"medium": 1},
                "contract_review_counts": {"no_failed_trajectory": 1},
                "failed_trajectory_count": 0,
                "failed_task_count": 0,
                "contract_issue_task_count": 0,
            },
            "tasks": [
                {
                    "task_id": "example-task",
                    "category": "workflow",
                    "metadata_size": "large",
                    "assigned_size": "medium",
                    "floor_passes": 1,
                    "floor_attempts": 3,
                    "ceiling_passes": 0,
                    "ceiling_attempts": 0,
                    "medium_smoke_passes": 1,
                    "medium_smoke_attempts": 1,
                    "task_contract_review": "no_failed_trajectory",
                    "failed_trajectory_count": 0,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.md"
            write_markdown(path, manifest)
            text = path.read_text()

        self.assertIn("not the formal Extra High ceiling gate", text)
        self.assertIn("| Floor | Extra High Ceiling | Medium Smoke |", text)
        self.assertIn("| `example-task` | workflow | large | medium | 1/3 | 0/0 | 1/1 |", text)
        self.assertNotIn("| Floor | Ceiling |", text)


if __name__ == "__main__":
    unittest.main()

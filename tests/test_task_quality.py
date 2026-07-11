from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.task_quality import build_task_quality_report


class TaskQualityReportTests(unittest.TestCase):
    def test_reports_evidence_complete_when_structured_quality_evidence_exists(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(
                root / "ready",
                calibration_status="candidate",
                with_quality=True,
                with_alternate=True,
            )

            report = build_task_quality_report(root)

        self.assertEqual(report["schema_version"], "shallowswe.task_quality.v0.1")
        self.assertTrue(report["quality_evidence_complete"])
        self.assertEqual(report["quality_evidence_complete_count"], 1)
        ready = _task(report, "ready")
        self.assertTrue(ready["quality_evidence_complete"])
        self.assertEqual(ready["quality_issues"], [])
        self.assertEqual(ready["quality_evidence"]["requirement_count"], 1)
        self.assertEqual(ready["quality_evidence"]["negative_control_count"], 1)

    def test_missing_quality_artifacts_block_evidence_completeness(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(
                root / "candidate",
                calibration_status="candidate",
                with_quality=False,
                with_alternate=True,
            )

            report = build_task_quality_report(root)

        self.assertFalse(report["quality_evidence_complete"])
        self.assertEqual(
            report["quality_issue_counts"],
            {
                "negative_controls_missing": 1,
                "requirement_map_missing": 1,
            },
        )

    def test_contract_notes_are_mapped_to_openai_failure_modes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(
                root / "repaired",
                calibration_status="candidate",
                with_quality=True,
                with_alternate=True,
                calibration_extra="""
[calibration.audit]
task_contract_review = "prompt_repaired_then_valid_success"
contract_issue = true
trajectory_audit = "First pass exposed an underspecified rule, then the prompt was repaired."
""",
            )

            report = build_task_quality_report(root)

        repaired = _task(report, "repaired")
        self.assertEqual(repaired["openai_failure_modes_seen"], ["underspecified_prompt"])
        self.assertIn("contract_issue_history", repaired["quality_labels"])
        self.assertEqual(report["openai_failure_mode_counts"]["underspecified_prompt"], 1)

    def test_alternate_solution_blocker_is_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(
                root / "blocked",
                calibration_status="candidate",
                with_quality=True,
                with_alternate=True,
                calibration_extra="""
[calibration.audit]
task_contract_review = "legitimate_model_miss"
alternate_solution_independent = false
alternate_solution_note = "solution_alt was a mechanical copy of the reference solution."
""",
            )

            report = build_task_quality_report(root)

        blocked = _task(report, "blocked")
        self.assertFalse(blocked["quality_evidence_complete"])
        self.assertEqual(
            blocked["alternate_solution_blocker"],
            "alternate_solution_marked_not_independent",
        )
        self.assertIn("alternate_solution_not_independent", blocked["quality_labels"])

    def test_invalid_quality_entries_do_not_count_as_complete_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "invalid"
            _write_task(
                task,
                calibration_status="candidate",
                with_quality=True,
                with_alternate=True,
            )
            (task / "quality" / "requirements.json").write_text(
                json.dumps(
                    {
                        "requirements": [
                            {
                                "id": "R1",
                                "source": "instruction.md",
                                "behavior": "perform the requested behavior",
                                "verifier_checks": [],
                            }
                        ]
                    }
                )
            )
            (task / "quality" / "negative-controls.json").write_text(
                json.dumps(
                    {
                        "negative_controls": [
                            {
                                "id": "NC1",
                                "description": "",
                                "expected_failure": "requested behavior is missing",
                            }
                        ]
                    }
                )
            )

            report = build_task_quality_report(root)

        self.assertFalse(report["quality_evidence_complete"])
        self.assertEqual(
            report["quality_issue_counts"],
            {
                "negative_controls_invalid_entry": 1,
                "requirement_map_invalid_entry": 1,
            },
        )

    def test_missing_verifier_reference_does_not_count_as_complete_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "invalid-reference"
            _write_task(
                task,
                calibration_status="candidate",
                with_quality=True,
                with_alternate=True,
            )
            payload = json.loads((task / "quality" / "requirements.json").read_text())
            payload["requirements"][0]["verifier_checks"] = [
                "tests/test.sh:MissingVerifierTests.test_missing"
            ]
            (task / "quality" / "requirements.json").write_text(json.dumps(payload))

            report = build_task_quality_report(root)

        invalid = _task(report, "invalid-reference")
        self.assertFalse(invalid["quality_evidence_complete"])
        self.assertEqual(
            invalid["quality_evidence"]["invalid_verifier_references"],
            ["tests/test.sh:MissingVerifierTests.test_missing"],
        )
        self.assertEqual(
            invalid["quality_issues"],
            ["requirement_map_invalid_verifier_reference"],
        )


def _task(report: dict[str, object], task_id: str) -> dict[str, object]:
    tasks = report["tasks"]
    assert isinstance(tasks, list)
    return next(task for task in tasks if task["task_id"] == task_id)


def _write_task(
    path: Path,
    *,
    calibration_status: str,
    with_quality: bool,
    with_alternate: bool,
    calibration_extra: str = "",
) -> None:
    path.mkdir()
    (path / "environment").mkdir()
    (path / "tests").mkdir()
    (path / "tests" / "test.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (path / "solution").mkdir()
    (path / "solution" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    if with_alternate:
        (path / "solution_alt").mkdir()
        (path / "solution_alt" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    if with_quality:
        (path / "quality").mkdir()
        (path / "quality" / "requirements.json").write_text(
            json.dumps(
                {
                    "requirements": [
                        {
                            "id": "R1",
                            "source": "instruction.md",
                            "behavior": "perform the requested behavior",
                            "verifier_checks": ["tests/test.sh"],
                        }
                    ]
                }
            )
        )
        (path / "quality" / "negative-controls.json").write_text(
            json.dumps(
                {
                    "negative_controls": [
                        {
                            "id": "NC1",
                            "description": "no-op solution",
                            "expected_failure": "requested behavior is missing",
                        }
                    ]
                }
            )
        )
    (path / "instruction.md").write_text("Do the task.\n")
    (path / "task.toml").write_text(
        f"""
[task]
name = "shallowswe/{path.name}"

[metadata]
category = "code"
size = "small"
calibration_status = "{calibration_status}"
{calibration_extra}
""".strip()
    )


if __name__ == "__main__":
    unittest.main()

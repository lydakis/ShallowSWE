from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shallowswe.admission import audit_task_admission


class AdmissionAuditTests(unittest.TestCase):
    def test_reports_ready_when_official_task_has_reference_and_alternate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(root / "ready", calibration_status="candidate", with_alternate=True)
            _write_task(root / "smoke", calibration_status="smoke", with_alternate=False)

            audit = audit_task_admission(root)

        self.assertTrue(audit["ready_for_snapshot"])
        self.assertEqual(audit["schema_version"], "shallowswe.admission_audit.v0.2")
        self.assertEqual(audit["official_task_count"], 1)
        self.assertEqual(audit["ready_task_count"], 1)
        ready = _task(audit, "ready")
        self.assertTrue(ready["ready_for_snapshot"])
        self.assertEqual(ready["admission_issues"], [])
        self.assertFalse(audit["ready_for_calibrated_snapshot"])
        self.assertEqual(audit["ready_for_calibrated_snapshot_count"], 0)
        self.assertEqual(audit["calibration_issue_counts"], {"missing_calibration_provenance": 1})
        self.assertEqual(ready["calibration_issues"], ["missing_calibration_provenance"])
        self.assertFalse(_task(audit, "smoke")["ready_for_calibrated_snapshot"])

    def test_reports_calibrated_ready_when_local_and_calibration_gates_are_accepted(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(
                root / "accepted",
                calibration_status="candidate",
                with_alternate=True,
                with_accepted_calibration=True,
            )

            audit = audit_task_admission(root)

        self.assertTrue(audit["ready_for_snapshot"])
        self.assertTrue(audit["ready_for_calibrated_snapshot"])
        self.assertEqual(audit["ready_for_calibrated_snapshot_count"], 1)
        accepted = _task(audit, "accepted")
        self.assertTrue(accepted["ready_for_calibrated_snapshot"])
        self.assertEqual(accepted["calibration_issues"], [])

    def test_missing_alternate_solution_blocks_official_task(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(root / "candidate", calibration_status="candidate", with_alternate=False)

            audit = audit_task_admission(root)

        self.assertFalse(audit["ready_for_snapshot"])
        self.assertEqual(audit["issue_counts"], {"missing_alternate_solution": 1})
        candidate = _task(audit, "candidate")
        self.assertFalse(candidate["ready_for_snapshot"])
        self.assertEqual(candidate["admission_issues"], ["missing_alternate_solution"])


def _task(audit: dict[str, object], task_id: str) -> dict[str, object]:
    tasks = audit["tasks"]
    assert isinstance(tasks, list)
    return next(task for task in tasks if task["task_id"] == task_id)


def _write_task(
    path: Path,
    *,
    calibration_status: str,
    with_alternate: bool,
    with_accepted_calibration: bool = False,
) -> None:
    path.mkdir()
    (path / "environment").mkdir()
    (path / "tests").mkdir()
    (path / "tests" / "test.sh").write_text(
        "#!/usr/bin/env bash\n"
        "python3 -m unittest discover\n"
        "status=$?\n"
        'exit "$status"\n'
    )
    (path / "solution").mkdir()
    (path / "solution" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    if with_alternate:
        (path / "solution_alt").mkdir()
        (path / "solution_alt" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    (path / "instruction.md").write_text("Do the task.\n")
    calibration = ""
    if with_accepted_calibration:
        calibration = """

[calibration]
calibration_snapshot_id = "test-snapshot"
admission_decision = "accepted"
size_assignment_decision = "accepted"

[calibration.ceiling]
one_shot_current_n = 16
one_shot_target_n = 16

[calibration.floor]
one_shot_current_n = 10
one_shot_target_n = 10
"""
    (path / "task.toml").write_text(
        f"""
[task]
name = "shallowswe/{path.name}"

[metadata]
category = "code"
size = "small"
calibration_status = "{calibration_status}"
{calibration}
""".strip()
    )


if __name__ == "__main__":
    unittest.main()

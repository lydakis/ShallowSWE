from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.task_quality import build_task_quality_report, quality_artifact_hashes


class ExecutedTaskQualityEvidenceTests(unittest.TestCase):
    def test_executed_evidence_and_independent_review_are_hash_bound(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _write_task(root / "ready")
            hashes = quality_artifact_hashes(task)
            _write_execution_evidence(task, hashes)
            _write_routine_review(task, hashes)

            ready = build_task_quality_report(root)["tasks"][0]

            self.assertTrue(ready["quality_evidence_complete"])
            self.assertTrue(ready["executed_quality_evidence_complete"])
            self.assertTrue(ready["routine_review_complete"])

            (task / "tests" / "test.sh").write_text("#!/usr/bin/env bash\nexit 2\n")
            stale = build_task_quality_report(root)["tasks"][0]

            self.assertFalse(stale["executed_quality_evidence_complete"])
            self.assertIn(
                "execution_evidence_stale_artifact_hashes",
                stale["executed_quality_issues"],
            )


def _write_task(path: Path) -> Path:
    (path / "environment").mkdir(parents=True)
    (path / "environment" / "fixture.txt").write_text("base\n")
    (path / "tests").mkdir()
    (path / "tests" / "test.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (path / "solution").mkdir()
    (path / "solution" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    (path / "solution_alt").mkdir()
    (path / "solution_alt" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    (path / "quality" / "negative-controls").mkdir(parents=True)
    (path / "instruction.md").write_text("Do the task.\n")
    (path / "task.toml").write_text(
        """
[task]
name = "shallowswe/ready"

[metadata]
category = "code"
size = "small"
calibration_status = "candidate"
""".strip()
        + "\n"
    )
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
                        "description": "no-op",
                        "expected_failure": "behavior remains missing",
                    }
                ]
            }
        )
    )
    return path


def _write_execution_evidence(task: Path, hashes: dict[str, str]) -> None:
    runs = [
        {
            "kind": "reference_solution",
            "attempt": attempt,
            "exit_code": 0,
            "clean_sandbox": True,
            "command": "solution/solve.sh && tests/test.sh",
            "output_sha256": "sha256:output",
            "artifact_sha256": "sha256:artifact",
        }
        for attempt in range(1, 4)
    ]
    runs.extend(
        [
            {
                "kind": "alternate_solution",
                "attempt": 1,
                "exit_code": 0,
                "clean_sandbox": True,
                "command": "solution_alt/solve.sh && tests/test.sh",
                "output_sha256": "sha256:output",
                "artifact_sha256": "sha256:artifact-alt",
            },
            {
                "kind": "negative_control",
                "control_id": "NC1",
                "attempt": 1,
                "exit_code": 1,
                "clean_sandbox": True,
                "command": "tests/test.sh",
                "output_sha256": "sha256:output",
                "artifact_sha256": "sha256:artifact-bad",
            },
        ]
    )
    (task / "quality" / "executions.json").write_text(
        json.dumps(
            {
                "schema_version": "shallowswe.task_quality_execution.v0.1",
                "task_id": task.name,
                "runtime": {
                    "backend": "apple_container",
                    "version": "1.0.0",
                    "platform": "linux/arm64",
                },
                "artifact_hashes": hashes,
                "runs": runs,
            }
        )
    )


def _write_routine_review(task: Path, hashes: dict[str, str]) -> None:
    rubric = {
        field: {"rating": "pass", "rationale": "The task meets this construct criterion."}
        for field in (
            "realism",
            "ordinary_frequency",
            "delegation_plausibility",
            "ambiguity_risk",
            "engineer_effort",
            "specialized_knowledge",
            "horizon_classification",
        )
    }
    (task / "quality" / "routine-review.json").write_text(
        json.dumps(
            {
                "schema_version": "shallowswe.routine_review.v0.1",
                "task_id": task.name,
                "reviewer_count": 1,
                "reviewer": {
                    "reviewer_id": "independent-reviewer",
                    "qualification": "software engineer",
                    "independent_from_task_author": True,
                },
                "decision": "accept",
                "rubric": rubric,
                "artifact_hashes": {
                    "instruction": hashes["instruction"],
                    "environment": hashes["environment"],
                },
            }
        )
    )


if __name__ == "__main__":
    unittest.main()

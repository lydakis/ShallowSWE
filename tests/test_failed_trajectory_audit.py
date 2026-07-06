from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_failed_trajectories.py"
SPEC = importlib.util.spec_from_file_location("audit_failed_trajectories", SCRIPT_PATH)
assert SPEC is not None
audit_failed_trajectories = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit_failed_trajectories)


class FailedTrajectoryAuditTests(unittest.TestCase):
    def test_collect_failed_trajectories_uses_reward_zero_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            job = tmp / "job"
            failed = job / "task-a__failed"
            passed_with_exception = job / "task-b__passed"
            for trial in (failed, passed_with_exception):
                (trial / "verifier").mkdir(parents=True)
                (trial / "verifier" / "test-stdout.txt").write_text("AssertionError: bad\n")
                (trial / "verifier" / "reward.txt").write_text("0\n")
                (trial / "result.json").write_text(json.dumps({"exception_info": {}}))

            progress = {
                "stages": {
                    "stage": {
                        "job_dir": str(job),
                        "completed_tasks": [
                            {
                                "task_id": "task-a",
                                "trial_name": "task-a__failed",
                                "passed": False,
                                "reward": 0.0,
                                "exception_type": None,
                            },
                            {
                                "task_id": "task-b",
                                "trial_name": "task-b__passed",
                                "passed": True,
                                "reward": 1.0,
                                "exception_type": "NonZeroAgentExitCodeError",
                            },
                        ],
                    }
                }
            }

            rows = audit_failed_trajectories.collect_failed_trajectories(progress)

        self.assertEqual([row["task_id"] for row in rows], ["task-a"])
        self.assertEqual(rows[0]["failure_signature"], "AssertionError: bad")

    def test_tagged_exit_code_reads_last_tag(self) -> None:
        self.assertEqual(
            audit_failed_trajectories.tagged_exit_code(
                "__SOLUTION_EXIT__=1\n__SOLUTION_EXIT__=0\n",
                "__SOLUTION_EXIT__",
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()

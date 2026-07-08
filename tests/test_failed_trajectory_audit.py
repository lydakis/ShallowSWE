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
WATCHER_PATH = REPO_ROOT / "scripts" / "watch_failed_trajectory_audit.py"
WATCHER_SPEC = importlib.util.spec_from_file_location(
    "watch_failed_trajectory_audit", WATCHER_PATH
)
assert WATCHER_SPEC is not None
watch_failed_trajectory_audit = importlib.util.module_from_spec(WATCHER_SPEC)
assert WATCHER_SPEC.loader is not None
WATCHER_SPEC.loader.exec_module(watch_failed_trajectory_audit)


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

    def test_collect_failed_trajectories_resolves_aggregated_retry_job_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            base_job = tmp / "base-job"
            retry_job = tmp / "retry-job"
            failed = retry_job / "task-a__retry"
            (failed / "verifier").mkdir(parents=True)
            (failed / "verifier" / "test-stdout.txt").write_text("AssertionError: retry bad\n")
            (failed / "verifier" / "reward.txt").write_text("0\n")
            (failed / "result.json").write_text(
                json.dumps({"exception_info": {"exception_type": "AssertionError"}})
            )

            progress = {
                "stages": {
                    "stage": {
                        "job_dirs": [str(base_job), str(retry_job)],
                        "completed_tasks": [
                            {
                                "task_id": "task-a",
                                "trial_name": "task-a__retry",
                                "passed": False,
                                "reward": 0.0,
                                "exception_type": None,
                            }
                        ],
                    }
                }
            }

            rows = audit_failed_trajectories.collect_failed_trajectories(progress)

        self.assertEqual(rows[0]["trial_dir"], str(failed))
        self.assertEqual(rows[0]["result_exception"], "AssertionError")
        self.assertEqual(rows[0]["failure_signature"], "AssertionError: retry bad")

    def test_tagged_exit_code_reads_last_tag(self) -> None:
        self.assertEqual(
            audit_failed_trajectories.tagged_exit_code(
                "__SOLUTION_EXIT__=1\n__SOLUTION_EXIT__=0\n",
                "__SOLUTION_EXIT__",
            ),
            0,
        )

    def test_failed_signature_tracks_failed_trials_only(self) -> None:
        progress = {
            "stages": {
                "stage": {
                    "completed_tasks": [
                        {"task_id": "a", "trial_name": "a__1", "passed": False, "reward": 0.0},
                        {"task_id": "b", "trial_name": "b__1", "passed": True, "reward": 1.0},
                    ]
                }
            }
        }
        signature, count = watch_failed_trajectory_audit.failed_signature(progress)
        progress["stages"]["stage"]["completed_tasks"].append(
            {"task_id": "c", "trial_name": "c__1", "passed": False, "reward": 0.0}
        )
        next_signature, next_count = watch_failed_trajectory_audit.failed_signature(progress)

        self.assertEqual(count, 1)
        self.assertEqual(next_count, 2)
        self.assertNotEqual(signature, next_signature)


if __name__ == "__main__":
    unittest.main()

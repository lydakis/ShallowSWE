from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_codex_subscription_sizing import (
    build_report,
    failed_task_ids,
    filter_task_metadata,
    task_ids_without_scored_rows,
    write_progress,
)


class CodexSubscriptionSizingTests(unittest.TestCase):
    def test_medium_smoke_does_not_count_as_extra_high_formal_ceiling(self) -> None:
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
                "medium": [{"task_id": "example-task", "passed": True}],
                "xhigh": [{"task_id": "example-task", "passed": False}],
            },
            floor_rows=[
                {"task_id": "example-task", "passed": True},
                {"task_id": "example-task", "passed": False},
                {"task_id": "example-task", "passed": False},
            ],
            status={
                "formal_ceiling": {
                    "reasoning_effort": "xhigh",
                },
                "stages": {
                    "floor_gpt54mini_low": {
                        "attempts_per_task": 3,
                    }
                }
            },
        )

        task = report["tasks"][0]

        self.assertEqual(report["formal_ceiling"]["model_config"], "openai/gpt-5.5[extra_high]")
        self.assertFalse(task["codex_5_5_formal_ceiling"]["passed"])
        self.assertTrue(task["codex_5_5_medium_smoke"]["passed"])
        self.assertEqual(task["provisional_floor_size"], "medium")

    def test_medium_only_report_is_smoke_with_extra_high_ceiling_pending(self) -> None:
        report = build_report(
            task_metadata=[
                {
                    "task_id": "example-task",
                    "category": "code",
                    "size": "large",
                    "calibration_status": "candidate",
                }
            ],
            ceiling_rows_by_effort={
                "medium": [{"task_id": "example-task", "passed": True}],
            },
            floor_rows=[],
            status={
                "stages": {
                    "ceiling_medium": {
                        "attempts_per_task": 1,
                    }
                }
            },
        )

        task = report["tasks"][0]

        self.assertEqual(report["formal_ceiling"]["model_config"], "openai/gpt-5.5[extra_high]")
        self.assertEqual(task["codex_5_5_formal_ceiling_effort"], "xhigh")
        self.assertEqual(task["codex_5_5_formal_ceiling"]["attempts"], 0)
        self.assertTrue(task["codex_5_5_medium_smoke"]["passed"])

    def test_legacy_medium_formal_status_is_downgraded_to_smoke(self) -> None:
        report = build_report(
            task_metadata=[
                {
                    "task_id": "example-task",
                    "category": "workflow",
                    "size": "large",
                    "calibration_status": "candidate",
                }
            ],
            ceiling_rows_by_effort={
                "medium": [{"task_id": "example-task", "passed": True}],
            },
            floor_rows=[],
            status={
                "formal_ceiling": {
                    "reasoning_effort": "medium",
                },
                "stages": {},
            },
        )

        task = report["tasks"][0]

        self.assertEqual(report["formal_ceiling"]["model_config"], "openai/gpt-5.5[extra_high]")
        self.assertEqual(task["codex_5_5_formal_ceiling_effort"], "xhigh")
        self.assertEqual(task["codex_5_5_formal_ceiling"]["attempts"], 0)
        self.assertTrue(task["codex_5_5_medium_smoke"]["passed"])

    def test_excluded_rows_retry_same_effort_instead_of_promoting(self) -> None:
        rows = [
            {
                "task_id": "provider-hiccup",
                "passed": False,
                "status": "excluded",
                "exclusion_reason": "provider_or_network_error",
            },
            {"task_id": "scored-failure", "passed": False, "status": "scored"},
            {"task_id": "scored-pass", "passed": True, "status": "scored"},
        ]

        self.assertEqual(
            task_ids_without_scored_rows(
                rows,
                ["provider-hiccup", "scored-failure", "scored-pass"],
            ),
            ["provider-hiccup"],
        )
        self.assertEqual(failed_task_ids(rows), ["scored-failure"])

    def test_excluded_extra_high_row_is_pending_formal_ceiling(self) -> None:
        report = build_report(
            task_metadata=[
                {
                    "task_id": "provider-hiccup",
                    "category": "code",
                    "size": "medium",
                    "calibration_status": "candidate",
                }
            ],
            ceiling_rows_by_effort={
                "medium": [{"task_id": "provider-hiccup", "passed": True, "status": "scored"}],
                "xhigh": [
                    {
                        "task_id": "provider-hiccup",
                        "passed": False,
                        "status": "excluded",
                        "exclusion_reason": "provider_or_network_error",
                    }
                ],
            },
            floor_rows=[],
            status={"formal_ceiling": {"reasoning_effort": "xhigh"}, "stages": {}},
        )

        task = report["tasks"][0]

        self.assertEqual(task["codex_5_5_formal_ceiling"]["attempts"], 0)
        self.assertEqual(task["codex_5_5_formal_ceiling"]["excluded"], 1)
        self.assertFalse(task["codex_5_5_formal_ceiling"]["scored_failure"])
        self.assertTrue(task["codex_5_5_medium_smoke"]["passed"])

    def test_include_task_filter_keeps_only_requested_tasks(self) -> None:
        rows = [
            {"task_id": "a"},
            {"task_id": "b"},
            {"task_id": "c"},
        ]

        self.assertEqual(
            filter_task_metadata(rows, ["c", "a", "a"]),
            [{"task_id": "a"}, {"task_id": "c"}],
        )

    def test_include_task_filter_rejects_unknown_tasks(self) -> None:
        with self.assertRaisesRegex(SystemExit, "Unknown task IDs requested: missing"):
            filter_task_metadata([{"task_id": "known"}], ["missing"])

    def test_progress_includes_recorded_retry_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results_dir = root / "results"
            jobs_dir = root / "jobs"
            results_dir.mkdir()

            base_job = jobs_dir / "base-job"
            retry_job = jobs_dir / "retry-job"
            self.write_result(base_job, "trial-a", "tasks/provider-hiccup", 0.0)
            self.write_result(retry_job, "trial-b", "tasks/provider-hiccup", 1.0)

            (results_dir / "status.json").write_text(
                json.dumps(
                    {
                        "stamp": "2026-07-06-000000",
                        "task_count": 1,
                        "jobs_dir": str(jobs_dir),
                        "formal_ceiling": {
                            "reasoning_effort": "xhigh",
                        },
                        "stages": {
                            "ceiling_xhigh": {
                                "job_name": "base-job",
                                "job_names": ["base-job", "retry-job"],
                            }
                        },
                    }
                )
            )

            write_progress(results_dir=results_dir)

            progress = json.loads((results_dir / "progress.json").read_text())
            ceiling = progress["stages"]["formal_ceiling_gpt55_xhigh"]

            self.assertEqual(ceiling["status"], "complete")
            self.assertEqual(ceiling["completed"], 2)
            self.assertEqual(ceiling["passes"], 1)
            self.assertEqual(ceiling["failures"], 1)
            self.assertEqual(ceiling["job_dirs"], [str(base_job), str(retry_job)])
            self.assertEqual(
                [row["job_dir"] for row in ceiling["completed_tasks"]],
                [str(base_job), str(retry_job)],
            )

    def test_progress_keeps_missing_recorded_retry_job_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results_dir = root / "results"
            jobs_dir = root / "jobs"
            results_dir.mkdir()

            base_job = jobs_dir / "base-job"
            retry_job = jobs_dir / "retry-job"
            self.write_result(base_job, "trial-a", "tasks/provider-hiccup", 0.0)

            (results_dir / "status.json").write_text(
                json.dumps(
                    {
                        "stamp": "2026-07-06-000000",
                        "task_count": 1,
                        "jobs_dir": str(jobs_dir),
                        "formal_ceiling": {
                            "reasoning_effort": "xhigh",
                        },
                        "stages": {
                            "ceiling_xhigh": {
                                "job_name": "base-job",
                                "job_names": ["base-job", "retry-job"],
                            }
                        },
                    }
                )
            )

            write_progress(results_dir=results_dir)

            progress = json.loads((results_dir / "progress.json").read_text())
            ceiling = progress["stages"]["formal_ceiling_gpt55_xhigh"]

            self.assertEqual(ceiling["status"], "running")
            self.assertEqual(ceiling["completed"], 1)
            self.assertEqual(ceiling["not_started_job_dirs"], [str(retry_job)])

    def test_progress_keeps_medium_stage_as_smoke_not_formal_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results_dir = root / "results"
            jobs_dir = root / "jobs"
            results_dir.mkdir()

            smoke_job = jobs_dir / "medium-smoke-job"
            self.write_result(smoke_job, "trial-a", "tasks/smoke-task", 1.0)

            (results_dir / "status.json").write_text(
                json.dumps(
                    {
                        "stamp": "2026-07-06-000000",
                        "task_count": 1,
                        "jobs_dir": str(jobs_dir),
                        "stages": {
                            "ceiling_medium": {
                                "job_name": "medium-smoke-job",
                                "job_names": ["medium-smoke-job"],
                            }
                        },
                    }
                )
            )

            write_progress(results_dir=results_dir)

            progress = json.loads((results_dir / "progress.json").read_text())

            self.assertIn("formal_ceiling_gpt55_xhigh", progress["stages"])
            self.assertNotIn("formal_ceiling_gpt55_medium", progress["stages"])
            self.assertEqual(
                progress["stages"]["formal_ceiling_gpt55_xhigh"]["status"],
                "not_started",
            )
            self.assertEqual(
                progress["stages"]["practical_smoke_gpt55_medium"]["status"],
                "complete",
            )
            self.assertEqual(progress["stages"]["practical_smoke_gpt55_medium"]["passes"], 1)

    def write_result(self, job_dir: Path, trial_name: str, task_name: str, reward: float) -> None:
        trial_dir = job_dir / trial_name
        trial_dir.mkdir(parents=True)
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "task_name": task_name,
                    "trial_name": trial_name,
                    "verifier_result": {"rewards": {"reward": reward}},
                }
            )
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import unittest

from shallowswe.task_quality_execution import (
    _artifact_hash_command,
    _docker_build_command,
    execute_task_quality,
)


class TaskQualityExecutionTests(unittest.TestCase):
    def test_artifact_hash_prefers_non_ignored_worktree_files(self) -> None:
        command = _artifact_hash_command()

        self.assertIn("git -C /app rev-parse --is-inside-work-tree", command)
        self.assertIn("git -C /app ls-files --cached --others --exclude-standard", command)
        self.assertIn("find /app -type f", command)
        self.assertIn("! -path '*/.git/*'", command)

    def test_docker_build_command_adds_optional_dns_override(self) -> None:
        task_path = Path("/tmp/task")
        image = "shallowswe-quality/task:local"

        self.assertEqual(
            _docker_build_command(task_path, image, build_dns=None),
            [
                "docker",
                "build",
                "--progress",
                "plain",
                "-t",
                image,
                "/tmp/task/environment",
            ],
        )
        self.assertEqual(
            _docker_build_command(task_path, image, build_dns="8.8.8.8"),
            [
                "docker",
                "build",
                "--progress",
                "plain",
                "--dns",
                "8.8.8.8",
                "-t",
                image,
                "/tmp/task/environment",
            ],
        )

    def test_execute_can_reuse_an_existing_local_image_without_building(self) -> None:
        task_path = Path("/tmp/task")
        inspect_payload = "sha256:image"

        def execute_run(*args, **kwargs):
            kind = kwargs["kind"]
            return {
                "kind": kind,
                "exit_code": 1 if kind == "pristine_submission" else 0,
                "verifier_reached": True,
            }

        with (
            patch("shallowswe.task_quality_execution._load_controls", return_value=[]),
            patch(
                "shallowswe.task_quality_execution._run_checked",
                side_effect=["Docker version 29.6.1", inspect_payload],
            ) as run_checked,
            patch(
                "shallowswe.task_quality_execution._execute_run",
                side_effect=execute_run,
            ),
            patch("shallowswe.task_quality_execution.quality_artifact_hashes", return_value={}),
            patch.object(Path, "write_text"),
        ):
            payload = execute_task_quality(task_path, reference_runs=1, reuse_image=True)

        self.assertEqual(payload["runtime"]["image_source"], "reused_local")
        self.assertEqual(payload["runtime"]["backend"], "docker")
        self.assertEqual(run_checked.call_count, 2)
        self.assertEqual(run_checked.call_args_list[0].args[0], ["docker", "--version"])

    def test_execute_rejects_a_passing_pristine_submission(self) -> None:
        task_path = Path("/tmp/task")

        def execute_run(*args, **kwargs):
            return {
                "kind": kwargs["kind"],
                "exit_code": 0,
                "verifier_reached": True,
            }

        with (
            patch("shallowswe.task_quality_execution._load_controls", return_value=[]),
            patch(
                "shallowswe.task_quality_execution._run_checked",
                side_effect=["Docker version 29.6.1", "sha256:image"],
            ),
            patch("shallowswe.task_quality_execution._execute_run", side_effect=execute_run),
            patch("shallowswe.task_quality_execution.quality_artifact_hashes", return_value={}),
            patch.object(Path, "write_text"),
        ):
            with self.assertRaisesRegex(RuntimeError, "pristine_submission"):
                execute_task_quality(task_path, reference_runs=1, reuse_image=True)


if __name__ == "__main__":
    unittest.main()

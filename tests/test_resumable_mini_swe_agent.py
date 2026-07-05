from __future__ import annotations

from pathlib import PurePosixPath
import unittest

from shallowswe.pier_agents.resumable_mini_swe_agent import _resume_aware_run_command


class ResumableMiniSweAgentCommandTests(unittest.TestCase):
    def test_resume_command_repairs_missing_mini_swe_install_before_running(self) -> None:
        command = _resume_aware_run_command(
            run_model_name="openrouter/example-model",
            instruction="Verification failed. Continue working.",
            remote_source_dir="/tmp/shallowswe-mini-swe-agent-fork",
            output_path=PurePosixPath("/logs/agent/mini-swe-agent.trajectory.json"),
            previous_path=PurePosixPath("/logs/agent/mini-swe-agent.previous.trajectory.json"),
            extra_flags="",
            config_flags="-c mini.yaml ",
            extra_python_packages=[],
        )

        self.assertIn("import minisweagent", command)
        self.assertIn("pip install /tmp/shallowswe-mini-swe-agent-fork", command)
        self.assertLess(
            command.index("import minisweagent"),
            command.index("mini-swe-agent --yolo"),
        )
        self.assertIn("--resume-from=/logs/agent/mini-swe-agent.previous.trajectory.json", command)


if __name__ == "__main__":
    unittest.main()

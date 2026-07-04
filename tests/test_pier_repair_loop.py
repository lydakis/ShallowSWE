from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from shallowswe.pier_repair_loop import _mini_swe_exit_status, _stop_reason_for_agent_exit


class PierRepairLoopTests(unittest.TestCase):
    def test_mini_swe_exit_status_reads_trajectory_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp)
            (agent_dir / "mini-swe-agent.trajectory.json").write_text(
                json.dumps({"info": {"exit_status": "LimitsExceeded"}})
            )
            trial = SimpleNamespace(_trial_paths=SimpleNamespace(agent_dir=agent_dir))

            self.assertEqual(_mini_swe_exit_status(trial), "LimitsExceeded")

    def test_mini_swe_exit_status_handles_missing_or_invalid_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp)
            trial = SimpleNamespace(_trial_paths=SimpleNamespace(agent_dir=agent_dir))

            self.assertIsNone(_mini_swe_exit_status(trial))

            (agent_dir / "mini-swe-agent.trajectory.json").write_text("{")

            self.assertIsNone(_mini_swe_exit_status(trial))

    def test_stop_reason_maps_limit_exit_to_agent_step_cap(self) -> None:
        self.assertEqual(_stop_reason_for_agent_exit("LimitsExceeded"), "agent_step_cap")
        self.assertEqual(_stop_reason_for_agent_exit("Blocked"), "agent_exit_blocked")
        self.assertEqual(_stop_reason_for_agent_exit(None), "agent_exit_unknown")


if __name__ == "__main__":
    unittest.main()

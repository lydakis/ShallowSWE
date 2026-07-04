from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from pier.models.agent.context import AgentContext

from shallowswe.pier_repair_loop import (
    _classify_agent_exit,
    _dollar_cap_hit,
    _mini_swe_exit_status,
    _stop_reason_for_agent_exit,
)


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
        self.assertEqual(_stop_reason_for_agent_exit("TimeExceeded"), "wall_time_cap")
        self.assertEqual(_stop_reason_for_agent_exit("Blocked"), "agent_exit_blocked")
        self.assertEqual(_stop_reason_for_agent_exit(None), "agent_exit_unknown")

    def test_dollar_cap_hit_uses_cumulative_context_cost(self) -> None:
        self.assertTrue(
            _dollar_cap_hit(context=AgentContext(cost_usd=1.5), dollar_cap_usd=1.5)
        )
        self.assertFalse(
            _dollar_cap_hit(context=AgentContext(cost_usd=1.49), dollar_cap_usd=1.5)
        )
        self.assertFalse(
            _dollar_cap_hit(context=AgentContext(cost_usd=1.5), dollar_cap_usd=None)
        )

    def test_classify_agent_exit_separates_dollar_step_and_wall_caps(self) -> None:
        self.assertEqual(
            _classify_agent_exit(
                exit_status="LimitsExceeded",
                context=AgentContext(cost_usd=2.0),
                dollar_cap_usd=1.5,
            ),
            ("dollar_cap", "scored", None),
        )
        self.assertEqual(
            _classify_agent_exit(
                exit_status="LimitsExceeded",
                context=AgentContext(cost_usd=1.0),
                dollar_cap_usd=1.5,
            ),
            ("agent_step_cap", "scored", None),
        )
        self.assertEqual(
            _classify_agent_exit(
                exit_status="TimeExceeded",
                context=AgentContext(cost_usd=0.0),
                dollar_cap_usd=1.5,
            ),
            ("wall_time_cap", "excluded", "infra_wall_time_guard"),
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import tempfile
import unittest

from pier.models.agent.context import AgentContext

from shallowswe.pier_repair_loop import (
    _classify_agent_exit,
    _classify_runner_exception,
    _dollar_cap_hit,
    _hide_verifier_artifacts,
    _mini_swe_exit_status,
    _stop_reason_for_agent_exit,
    _verify_submission,
)


class PierRepairLoopTests(unittest.TestCase):
    def test_hide_verifier_artifacts_empties_tests_and_verifier_logs(self) -> None:
        calls = []

        class FakeEnvironment:
            env_paths = SimpleNamespace(
                verifier_dir="/logs/verifier",
                tests_dir="/tests",
            )

            async def empty_dirs(self, dirs, *, chmod=True):
                calls.append((list(dirs), chmod))
                return SimpleNamespace(return_code=0, stdout="", stderr="")

        trial = SimpleNamespace(_environment=FakeEnvironment())

        asyncio.run(_hide_verifier_artifacts(trial))

        self.assertEqual(calls, [(["/logs/verifier", "/tests"], False)])

    def test_hide_verifier_artifacts_raises_when_cleanup_fails(self) -> None:
        class FakeEnvironment:
            env_paths = SimpleNamespace(
                verifier_dir="/logs/verifier",
                tests_dir="/tests",
            )

            async def empty_dirs(self, dirs, *, chmod=True):
                return SimpleNamespace(return_code=1, stdout="", stderr="permission denied")

        trial = SimpleNamespace(_environment=FakeEnvironment())

        with self.assertRaisesRegex(RuntimeError, "Failed to hide verifier artifacts"):
            asyncio.run(_hide_verifier_artifacts(trial))

    def test_verify_submission_removes_tests_and_logs_after_verifier_run(self) -> None:
        calls = []

        class FakeEnvironment:
            default_user = None
            env_paths = SimpleNamespace(
                verifier_dir="/logs/verifier",
                tests_dir="/tests",
            )

            async def reset_dirs(self, **kwargs):
                calls.append(kwargs)

            async def empty_dirs(self, dirs, *, chmod=True):
                calls.append((list(dirs), chmod))
                return SimpleNamespace(return_code=0, stdout="", stderr="")

        class FakeTrial:
            _environment = FakeEnvironment()
            _task = SimpleNamespace(config=SimpleNamespace(verifier=SimpleNamespace(user="verifier")))

            async def _verify_once(self, step_cfg):
                self.seen_default_user = self._environment.default_user
                return "verifier-result"

        trial = FakeTrial()

        result = asyncio.run(_verify_submission(trial))

        self.assertEqual(result, "verifier-result")
        self.assertEqual(trial.seen_default_user, "verifier")
        self.assertIsNone(trial._environment.default_user)
        self.assertEqual(
            calls,
            [
                {
                    "remove_dirs": ["/logs/verifier", "/tests"],
                    "create_dirs": ["/logs/verifier", "/tests"],
                    "chmod_dirs": ["/logs/verifier"],
                },
                (["/logs/verifier", "/tests"], False),
            ],
        )

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
            ("wall_time_cap", "scored", None),
        )

    def test_classify_runner_exception_excludes_infra_failures(self) -> None:
        self.assertEqual(
            _classify_runner_exception(),
            ("runner_exception", "excluded", "runner_infrastructure_error"),
        )


if __name__ == "__main__":
    unittest.main()

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
    _final_usage_totals,
    _hide_verifier_artifacts,
    _mini_swe_exit_status,
    _raw_usage_totals_from_trajectory,
    _sampling_config_from_file,
    _stop_reason_for_agent_exit,
    _tree_sha256,
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

    def test_dollar_cap_hit_uses_reported_trajectory_cost_before_raw_cost_sum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trajectory = Path(tmp) / "mini-swe-agent.trajectory.json"
            trajectory.write_text(
                json.dumps(
                    {
                        "info": {"model_stats": {"instance_cost": 1.0}},
                        "messages": [
                            {"response": {"usage": {"prompt_tokens": 10, "cost": 0.75}}},
                            {"response": {"usage": {"prompt_tokens": 10, "cost": 0.80}}},
                        ]
                    }
                )
            )

            self.assertFalse(
                _dollar_cap_hit(
                    context=AgentContext(),
                    dollar_cap_usd=1.5,
                    trajectory_path=trajectory,
                )
            )

    def test_final_usage_totals_use_raw_tokens_but_reported_trajectory_cost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trajectory = Path(tmp) / "mini-swe-agent.trajectory.json"
            trajectory.write_text(
                json.dumps(
                    {
                        "info": {"model_stats": {"instance_cost": 0.42}},
                        "messages": [
                            {
                                "response": {
                                    "usage": {
                                        "prompt_tokens": 100,
                                        "completion_tokens": 20,
                                        "cost": 0.30,
                                        "prompt_tokens_details": {
                                            "cached_tokens": 40,
                                            "cache_write_tokens": 5,
                                        },
                                        "completion_tokens_details": {
                                            "reasoning_tokens": 7,
                                        },
                                    }
                                }
                            },
                            {
                                "response": {
                                    "usage": {
                                        "input_tokens": 50,
                                        "output_tokens": 10,
                                        "cost": 0.25,
                                        "input_tokens_details": {
                                            "cached_tokens": 15,
                                            "cache_write_tokens": 3,
                                        },
                                        "output_tokens_details": {
                                            "reasoning_tokens": 2,
                                        },
                                    }
                                }
                            },
                        ]
                    }
                )
            )

            totals = _final_usage_totals(
                AgentContext(
                    n_input_tokens=1,
                    n_output_tokens=1,
                    n_cache_tokens=1,
                    cost_usd=0.01,
                ),
                trajectory,
            )

        self.assertEqual(totals["input_tokens"], 150)
        self.assertEqual(totals["output_tokens"], 30)
        self.assertEqual(totals["cache_read_tokens"], 55)
        self.assertEqual(totals["cache_write_tokens"], 8)
        self.assertEqual(totals["reasoning_tokens"], 9)
        self.assertAlmostEqual(totals["gateway_reported_cost_usd"], 0.42)

    def test_raw_usage_totals_return_none_without_usage_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trajectory = Path(tmp) / "mini-swe-agent.trajectory.json"
            trajectory.write_text(json.dumps({"messages": []}))

            self.assertIsNone(_raw_usage_totals_from_trajectory(trajectory))

    def test_raw_usage_totals_count_cache_creation_token_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trajectory = Path(tmp) / "mini-swe-agent.trajectory.json"
            trajectory.write_text(
                json.dumps(
                    {
                        "messages": [
                            {
                                "response": {
                                    "usage": {
                                        "prompt_tokens": 100,
                                        "completion_tokens": 20,
                                        "prompt_tokens_details": {
                                            "cache_creation_tokens": 30,
                                        },
                                    },
                                },
                            },
                            {
                                "response": {
                                    "usage": {
                                        "input_tokens": 50,
                                        "output_tokens": 10,
                                        "cache_creation_input_tokens": 7,
                                    },
                                },
                            },
                        ],
                    }
                )
            )

            totals = _raw_usage_totals_from_trajectory(trajectory)

        self.assertIsNotNone(totals)
        assert totals is not None
        self.assertEqual(totals["cache_write_tokens"], 37)

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

    def test_tree_sha256_is_stable_and_path_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "b.txt").write_text("two")
            (root / "tests" / "a.txt").write_text("one")

            digest = _tree_sha256(root / "tests")

            self.assertIsNotNone(digest)
            self.assertTrue(digest.startswith("sha256:"))
            self.assertEqual(digest, _tree_sha256(root / "tests"))

            (root / "tests" / "nested").mkdir()
            (root / "tests" / "nested" / "a.txt").write_text("one")

            self.assertNotEqual(digest, _tree_sha256(root / "tests"))

    def test_sampling_config_from_file_records_model_and_effort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(
                json.dumps(
                    {
                        "model": {
                            "temperature": 0,
                            "model_kwargs": {"max_tokens": 8192},
                        }
                    }
                )
            )

            sampling = _sampling_config_from_file(
                config_file=config_file,
                model_name="openrouter/example/model",
                reasoning_effort="low",
            )

            self.assertEqual(sampling["config_file"], str(config_file))
            self.assertEqual(sampling["model_name"], "openrouter/example/model")
            self.assertEqual(sampling["temperature"], 0)
            self.assertEqual(
                sampling["model_kwargs"],
                {"max_tokens": 8192, "reasoning_effort": "low"},
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.pier_export import export_pier_job, _status


class PierExportTests(unittest.TestCase):
    def test_exports_trial_rows_with_shallowswe_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            task = tasks / "sample-task"
            task.mkdir(parents=True)
            (task / "task.toml").write_text(
                """
[task]
name = "shallowswe/sample-task"

[metadata]
category = "fix"
tier = "t1"
language = "python"
subtype = "single-function-bugfix"
""".strip()
            )

            job = root / "job"
            trial = job / "sample-task__abc"
            trial.mkdir(parents=True)
            (trial / "result.json").write_text(
                json.dumps(
                    {
                        "task_name": "shallowswe/sample-task",
                        "task_id": {"path": "tasks/sample-task"},
                        "agent_info": {
                            "name": "mini-swe-agent",
                            "version": "2.4.4",
                            "model_info": {"name": "openai/example", "provider": "openai"},
                        },
                        "agent_result": {
                            "n_input_tokens": 100,
                            "n_cache_tokens": 10,
                            "n_output_tokens": 20,
                            "cost_usd": 0.01,
                            "peak_context_tokens": 90,
                            "n_agent_steps": 3,
                        },
                        "verifier_result": {"rewards": {"reward": 1.0}},
                        "started_at": "2026-07-03T10:00:00Z",
                        "finished_at": "2026-07-03T10:00:12Z",
                    }
                )
            )
            agent_dir = trial / "agent"
            agent_dir.mkdir()
            (agent_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "agent": {
                            "model_name": "openai/example",
                            "extra": {
                                "agent_config": {
                                    "system_template": "system",
                                    "instance_template": "instance",
                                }
                            },
                        },
                        "final_metrics": {
                            "total_prompt_tokens": 100,
                            "total_completion_tokens": 20,
                            "total_cached_tokens": 10,
                        },
                    }
                )
            )
            (agent_dir / "mini-swe-agent.trajectory.json").write_text(
                json.dumps(
                    {
                        "info": {
                            "config": {
                                "model": {
                                    "model_kwargs": {
                                        "reasoning_effort": "low",
                                    }
                                }
                            }
                        },
                        "messages": [
                            {
                                "response": {
                                    "model": "example-2026-01-01",
                                    "usage": {
                                        "prompt_tokens": 100,
                                        "completion_tokens": 20,
                                        "cost": 0.01,
                                        "prompt_tokens_details": {
                                            "cached_tokens": 10,
                                            "cache_write_tokens": 0,
                                        },
                                        "completion_tokens_details": {
                                            "reasoning_tokens": 5
                                        },
                                    },
                                }
                            }
                        ]
                    }
                )
            )

            rows = export_pier_job(job, tasks)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].model, "openai/example")
        self.assertEqual(rows[0].task_id, "sample-task")
        self.assertEqual(rows[0].category, "code")
        self.assertEqual(rows[0].size, "small")
        self.assertEqual(rows[0].tier, "small")
        self.assertTrue(rows[0].passed)
        self.assertEqual(rows[0].provider, "openai")
        self.assertEqual(rows[0].inference_gateway, "openai")
        self.assertEqual(rows[0].upstream_provider, "openai")
        self.assertEqual(rows[0].requested_model, "openai/example")
        self.assertEqual(rows[0].resolved_model, "example-2026-01-01")
        self.assertEqual(rows[0].reasoning_effort, "low")
        self.assertEqual(rows[0].input_tokens, 100)
        self.assertEqual(rows[0].output_tokens, 20)
        self.assertEqual(rows[0].cache_read_tokens, 10)
        self.assertEqual(rows[0].cache_write_tokens, 0)
        self.assertEqual(rows[0].reasoning_tokens, 5)
        self.assertEqual(rows[0].gateway_reported_cost_usd, 0.01)
        self.assertEqual(rows[0].turns, 3)
        self.assertEqual(rows[0].peak_context_tokens, 90)
        self.assertEqual(rows[0].status, "scored")
        self.assertIsNone(rows[0].exclusion_reason)
        self.assertEqual(rows[0].started_at, "2026-07-03T10:00:00Z")
        self.assertEqual(rows[0].finished_at, "2026-07-03T10:00:12Z")
        self.assertEqual(rows[0].agent, "mini-swe-agent")
        self.assertEqual(rows[0].agent_version, "2.4.4")
        self.assertEqual(rows[0].runner, "pier")
        self.assertEqual(rows[0].token_source, "pier_atif_final_metrics_reconciled")
        self.assertIsNotNone(rows[0].scaffold_prompt_hash)

    def test_provider_error_exports_as_excluded(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            task = tasks / "sample-task"
            task.mkdir(parents=True)
            (task / "task.toml").write_text(
                """
[task]
name = "shallowswe/sample-task"

[metadata]
category = "fix"
tier = "t1"
language = "python"
subtype = "single-function-bugfix"
""".strip()
            )

            job = root / "job"
            trial = job / "sample-task__abc"
            trial.mkdir(parents=True)
            (trial / "result.json").write_text(
                json.dumps(
                    {
                        "task_name": "shallowswe/sample-task",
                        "agent_info": {
                            "name": "mini-swe-agent",
                            "version": "2.4.4",
                            "model_info": {
                                "name": "openai/example",
                                "provider": "openrouter",
                            },
                        },
                        "agent_result": {
                            "n_input_tokens": 0,
                            "n_cache_tokens": 0,
                            "n_output_tokens": 0,
                            "n_agent_steps": 0,
                        },
                        "exception_info": {
                            "exception_type": "NonZeroAgentExitCodeError",
                            "exception_message": "OpenRouterAPIError: HTTP 402: requires more credits",
                        },
                        "verifier_result": {"rewards": {"reward": 0.0}},
                    }
                )
            )
            agent_dir = trial / "agent"
            agent_dir.mkdir()
            (agent_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "final_metrics": {
                            "total_prompt_tokens": 0,
                            "total_completion_tokens": 0,
                            "total_cached_tokens": 0,
                        }
                    }
                )
            )

            rows = export_pier_job(job, tasks)

        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].passed)
        self.assertEqual(rows[0].status, "excluded")
        self.assertEqual(rows[0].exclusion_reason, "provider_or_network_error")
        self.assertEqual(rows[0].inference_gateway, "openrouter")
        self.assertEqual(rows[0].upstream_provider, "openai")

    def test_non_provider_exception_with_network_words_stays_scored(self) -> None:
        with TemporaryDirectory() as tmp:
            status, exclusion_reason = _status(
                {
                    "exception_info": {
                        "exception_type": "AssertionError",
                        "exception_message": (
                            "expected network_connection_count to remain in the report"
                        ),
                    }
                },
                Path(tmp),
            )

        self.assertEqual(status, "scored")
        self.assertIsNone(exclusion_reason)

    def test_provider_5xx_error_exports_as_excluded(self) -> None:
        with TemporaryDirectory() as tmp:
            status, exclusion_reason = _status(
                {
                    "exception_info": {
                        "exception_type": "NonZeroAgentExitCodeError",
                        "exception_message": "Request failed: HTTP 503 Service Unavailable",
                    }
                },
                Path(tmp),
            )

        self.assertEqual(status, "excluded")
        self.assertEqual(exclusion_reason, "provider_or_network_error")

    def test_runner_infrastructure_error_exports_as_excluded(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            task = tasks / "sample-task"
            task.mkdir(parents=True)
            (task / "task.toml").write_text(
                """
[task]
name = "shallowswe/sample-task"

[metadata]
category = "fix"
tier = "t1"
language = "python"
subtype = "single-function-bugfix"
""".strip()
            )

            job = root / "job"
            trial = job / "sample-task__abc"
            trial.mkdir(parents=True)
            (trial / "result.json").write_text(
                json.dumps(
                    {
                        "task_name": "shallowswe/sample-task",
                        "task_id": {"path": "tasks/sample-task"},
                        "agent_info": {
                            "name": "mini-swe-agent",
                            "model_info": {
                                "name": "openai/example",
                                "provider": "openai",
                            },
                        },
                        "agent_result": {"n_agent_steps": 3},
                        "exception_info": {
                            "exception_type": "CancelledError",
                            "exception_traceback": "asyncio.exceptions.CancelledError",
                        },
                        "verifier_result": {"rewards": {"reward": 0.0}},
                    }
                )
            )
            agent_dir = trial / "agent"
            agent_dir.mkdir()
            (agent_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "final_metrics": {
                            "total_prompt_tokens": 100,
                            "total_completion_tokens": 20,
                            "total_cached_tokens": 10,
                        }
                    }
                )
            )
            (agent_dir / "mini-swe-agent.trajectory.json").write_text(
                json.dumps(
                    {
                        "messages": [
                            {
                                "response": {
                                    "model": "example-2026-01-01",
                                    "usage": {
                                        "prompt_tokens": 150,
                                        "completion_tokens": 25,
                                        "prompt_tokens_details": {"cached_tokens": 30},
                                    },
                                }
                            }
                        ]
                    }
                )
            )

            rows = export_pier_job(job, tasks)

        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].passed)
        self.assertEqual(rows[0].status, "excluded")
        self.assertEqual(rows[0].exclusion_reason, "runner_infrastructure_error")
        self.assertEqual(rows[0].input_tokens, 150)
        self.assertEqual(rows[0].output_tokens, 25)
        self.assertEqual(rows[0].cache_read_tokens, 30)
        self.assertEqual(rows[0].token_source, "raw_provider_usage_unreconciled_excluded")

    def test_docker_setup_error_exports_as_runner_infrastructure(self) -> None:
        with TemporaryDirectory() as tmp:
            status, exclusion_reason = _status(
                {
                    "exception_info": {
                        "exception_type": "RuntimeError",
                        "exception_message": (
                            "Docker compose command failed: no space left on device"
                        ),
                    }
                },
                Path(tmp),
            )

        self.assertEqual(status, "excluded")
        self.assertEqual(exclusion_reason, "runner_infrastructure_error")

    def test_rejects_unreconciled_token_totals(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            task = tasks / "sample-task"
            task.mkdir(parents=True)
            (task / "task.toml").write_text(
                """
[task]
name = "shallowswe/sample-task"

[metadata]
category = "fix"
tier = "t1"
language = "python"
subtype = "single-function-bugfix"
""".strip()
            )

            job = root / "job"
            trial = job / "sample-task__abc"
            trial.mkdir(parents=True)
            (trial / "result.json").write_text(
                json.dumps(
                    {
                        "task_name": "shallowswe/sample-task",
                        "task_id": {"path": "tasks/sample-task"},
                        "agent_info": {
                            "name": "mini-swe-agent",
                            "model_info": {"name": "openai/example", "provider": "openai"},
                        },
                        "agent_result": {"n_agent_steps": 3},
                        "verifier_result": {"rewards": {"reward": 1.0}},
                    }
                )
            )
            agent_dir = trial / "agent"
            agent_dir.mkdir()
            (agent_dir / "trajectory.json").write_text(
                json.dumps(
                    {
                        "final_metrics": {
                            "total_prompt_tokens": 100,
                            "total_completion_tokens": 20,
                            "total_cached_tokens": 10,
                        }
                    }
                )
            )
            (agent_dir / "mini-swe-agent.trajectory.json").write_text(
                json.dumps(
                    {
                        "messages": [
                            {
                                "response": {
                                    "model": "example-2026-01-01",
                                    "usage": {
                                        "prompt_tokens": 99,
                                        "completion_tokens": 20,
                                        "prompt_tokens_details": {"cached_tokens": 10},
                                    },
                                }
                            }
                        ]
                    }
                )
            )

            with self.assertRaisesRegex(ValueError, "token totals mismatch"):
                export_pier_job(job, tasks)

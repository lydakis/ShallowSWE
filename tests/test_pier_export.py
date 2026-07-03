from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.pier_export import export_pier_job


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
                        "messages": [
                            {
                                "response": {
                                    "model": "example-2026-01-01",
                                    "usage": {
                                        "prompt_tokens": 100,
                                        "completion_tokens": 20,
                                        "prompt_tokens_details": {"cached_tokens": 10},
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
        self.assertEqual(rows[0].category, "fix")
        self.assertEqual(rows[0].tier, "t1")
        self.assertTrue(rows[0].passed)
        self.assertEqual(rows[0].provider, "openai")
        self.assertEqual(rows[0].inference_gateway, "openai")
        self.assertEqual(rows[0].upstream_provider, "openai")
        self.assertEqual(rows[0].requested_model, "openai/example")
        self.assertEqual(rows[0].resolved_model, "example-2026-01-01")
        self.assertEqual(rows[0].input_tokens, 100)
        self.assertEqual(rows[0].output_tokens, 20)
        self.assertEqual(rows[0].cache_read_tokens, 10)
        self.assertEqual(rows[0].cache_write_tokens, 0)
        self.assertEqual(rows[0].turns, 3)
        self.assertEqual(rows[0].peak_context_tokens, 90)
        self.assertEqual(rows[0].status, "scored")
        self.assertIsNone(rows[0].exclusion_reason)
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

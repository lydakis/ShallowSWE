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
                            "model_info": {"name": "openai/example"},
                        },
                        "agent_result": {
                            "n_input_tokens": 100,
                            "n_cache_tokens": 10,
                            "n_output_tokens": 20,
                            "cost_usd": 0.01,
                            "n_agent_steps": 3,
                        },
                        "verifier_result": {"rewards": {"reward": 1.0}},
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
        self.assertEqual(rows[0].turns, 3)

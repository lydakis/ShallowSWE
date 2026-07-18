from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.kaggle_bound_source import write_bound_kaggle_task_sources


class KaggleTaskSourceTests(unittest.TestCase):
    def test_writes_one_hash_bound_source_per_ready_unit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "runner.py"
            source.write_text(
                'FROZEN_RUN_UNIT_ID: str | None = None\n'
                '@kbench.task(\n    name="shallowswe-repair-loop-v2",\n)\n'
            )
            run_spec = root / "run-spec.json"
            run_spec.write_text(
                json.dumps(
                    {
                        "schema_version": "shallowswe.run_spec.v0.1",
                        "run_spec_id": "test-run",
                        "experiment_id": "test-experiment",
                        "task_suite_version": "test-suite",
                        "model_configs": [
                            {
                                "model_config_id": "model-id",
                                "canonical": {
                                    "requested_model": "model-name",
                                    "expected_resolved_model": "model-name",
                                },
                            }
                        ],
                        "agent_policies": [
                            {
                                "agent_policy_id": "agent-id",
                                "canonical": {"agent": "mini-swe-agent"},
                            }
                        ],
                        "units": [
                            {
                                "run_unit_id": "unit-one",
                                "runner": "kaggle",
                                "kaggle_task_name": "unit-one",
                                "model_config_id": "model-id",
                                "agent_policy_id": "agent-id",
                                "task_ids": ["task-a"],
                                "rollout_seeds": [0],
                                "limits": {
                                    "verifier_submissions": 3,
                                    "agent_steps": 20,
                                    "wall_time_seconds": 120,
                                },
                            },
                        ],
                    }
                )
            )

            report = write_bound_kaggle_task_sources(source, run_spec, root / "out")

            self.assertEqual(report["source_count"], 1)
            generated = (root / "out" / "unit-one.py").read_text()
            self.assertIn('FROZEN_RUN_UNIT_ID: str | None = "unit-one"', generated)
            self.assertIn('name="unit-one"', generated)
            self.assertNotIn("plu_blocked", generated)
            self.assertTrue(report["sources"][0]["sha256"].startswith("sha256:"))

    def test_rejects_source_without_exact_freeze_markers(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "runner.py"
            source.write_text("print('unbound')\n")
            run_spec = root / "run.json"
            run_spec.write_text(json.dumps({}))

            with self.assertRaisesRegex(ValueError, "run-unit marker"):
                write_bound_kaggle_task_sources(source, run_spec, root / "out")

    def test_rejects_non_kaggle_units(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "runner.py"
            source.write_text(
                'FROZEN_RUN_UNIT_ID: str | None = None\n'
                '@kbench.task(\n    name="shallowswe-repair-loop-v2",\n)\n'
            )
            spec = {
                "schema_version": "shallowswe.run_spec.v0.1",
                "run_spec_id": "test-run",
                "experiment_id": "test-experiment",
                "task_suite_version": "test-suite",
                "model_configs": [
                    {
                        "model_config_id": "model-id",
                        "canonical": {
                            "requested_model": "model-name",
                            "expected_resolved_model": "model-name",
                        },
                    }
                ],
                "agent_policies": [
                    {"agent_policy_id": "agent-id", "canonical": {"agent": "agent"}}
                ],
                "units": [
                    {
                        "run_unit_id": "pier-unit",
                        "runner": "pier",
                        "model_config_id": "model-id",
                        "agent_policy_id": "agent-id",
                        "task_ids": ["task-a"],
                        "rollout_seeds": [0],
                        "limits": {
                            "verifier_submissions": 3,
                            "agent_steps": 20,
                            "wall_time_seconds": 120,
                        },
                    }
                ],
            }
            run_spec = root / "run-spec.json"
            run_spec.write_text(json.dumps(spec))

            with self.assertRaisesRegex(ValueError, "runner='kaggle'"):
                write_bound_kaggle_task_sources(source, run_spec, root / "out")


if __name__ == "__main__":
    unittest.main()

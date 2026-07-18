from __future__ import annotations

import unittest

from shallowswe.identity import agent_policy_id, model_config_id
from shallowswe.run_spec import (
    audit_run_spec,
    resolve_agent_policy,
    resolve_execution_sampling,
    resolve_model_config,
    resolve_run_unit,
    trajectory_id,
    unit_matrix,
    validate_run_spec,
)


class RunSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        low = {
            "requested_model": "gpt-5.6-sol",
            "expected_resolved_model": "gpt-5.6-sol",
            "reasoning_effort": "low",
            "sampling_config": {"temperature": 0.0},
        }
        high = {
            "requested_model": "gpt-5.6-sol",
            "expected_resolved_model": "gpt-5.6-sol",
            "reasoning_effort": "high",
            "sampling_config": {"temperature": 0.0},
        }
        agent = {"agent": "mini-swe-agent"}
        self.low_id = model_config_id(low)
        self.high_id = model_config_id(high)
        self.agent_id = agent_policy_id(agent)
        self.spec = {
            "schema_version": "shallowswe.run_spec.v0.1",
            "run_spec_id": "six-task-shakedown-v1",
            "experiment_id": "weekend-shakedown",
            "task_suite_version": "six-task-v1",
            "model_configs": [
                {
                    "model_config_id": self.low_id,
                    "canonical": low,
                },
                {
                    "model_config_id": self.high_id,
                    "canonical": high,
                },
            ],
            "agent_policies": [
                {"agent_policy_id": self.agent_id, "canonical": agent}
            ],
            "units": [
                {
                    "run_unit_id": "sol-low-all",
                    "runner": "kaggle",
                    "kaggle_task_name": "shallowswe-sol-low-all",
                    "model_config_id": self.low_id,
                    "agent_policy_id": self.agent_id,
                    "task_ids": ["task-a", "task-b"],
                    "rollout_seeds": [4000, 4001],
                    "limits": {
                        "verifier_submissions": 5,
                        "agent_steps": 80,
                        "wall_time_seconds": 2400,
                        "dollar_usd": 5.0,
                    },
                    "metadata": {"phase": "candidate_panel", "label": "cheap baseline"},
                }
            ],
        }

    def test_resolves_exact_execution_facts_and_keeps_metadata_opaque(self) -> None:
        validate_run_spec(self.spec)
        unit = resolve_run_unit(self.spec, "sol-low-all")
        model = resolve_model_config(self.spec, unit, observed_model="gpt-5.6-sol")
        policy = resolve_agent_policy(self.spec, unit)

        self.assertEqual(unit_matrix(unit), (["task-a", "task-b"], [4000, 4001]))
        self.assertEqual(model["canonical"]["reasoning_effort"], "low")
        self.assertEqual(policy["agent_policy_id"], self.agent_id)
        self.assertEqual(unit["metadata"]["phase"], "candidate_panel")
        self.assertEqual(
            trajectory_id(self.spec, unit, task_id="task-b", rollout_seed=4001),
            "six-task-shakedown-v1__sol-low-all__task-b__seed-4001",
        )

    def test_rejects_model_effort_collapse(self) -> None:
        unit = resolve_run_unit(self.spec, "sol-low-all")
        unit["model_config_id"] = self.high_id

        with self.assertRaisesRegex(RuntimeError, "does not match"):
            resolve_model_config(self.spec, unit, observed_model="different-model")

    def test_rejects_unregistered_task_or_seed(self) -> None:
        unit = resolve_run_unit(self.spec, "sol-low-all")

        with self.assertRaisesRegex(RuntimeError, "not registered"):
            trajectory_id(self.spec, unit, task_id="task-a", rollout_seed=9)

    def test_registered_sampling_ignores_external_fallbacks(self) -> None:
        temperature, task_suite_version = resolve_execution_sampling(
            self.spec,
            self.spec["model_configs"][0],
            fallback_temperature=1.0,
            fallback_task_suite_version="external-suite",
        )

        self.assertEqual(temperature, 0.0)
        self.assertEqual(task_suite_version, "six-task-v1")

    def test_unregistered_sampling_uses_external_fallbacks(self) -> None:
        temperature, task_suite_version = resolve_execution_sampling(
            None,
            None,
            fallback_temperature=0.25,
            fallback_task_suite_version="smoke-suite",
        )

        self.assertEqual(temperature, 0.25)
        self.assertEqual(task_suite_version, "smoke-suite")

    def test_rejects_invalid_limits_without_reading_metadata_labels(self) -> None:
        self.spec["units"][0]["limits"]["verifier_submissions"] = 0

        with self.assertRaisesRegex(ValueError, "verifier_submissions"):
            validate_run_spec(self.spec)

    def test_rejects_stale_model_content_id(self) -> None:
        self.spec["model_configs"][0]["canonical"]["reasoning_effort"] = "medium"

        with self.assertRaisesRegex(ValueError, "model_config_id does not match"):
            validate_run_spec(self.spec)

    def test_rejects_stale_agent_policy_content_id(self) -> None:
        self.spec["agent_policies"][0]["canonical"]["agent"] = "different-agent"

        with self.assertRaisesRegex(ValueError, "agent_policy_id does not match"):
            validate_run_spec(self.spec)

    def test_schema_accepts_a_transport_name_without_interpreting_it(self) -> None:
        self.spec["units"][0]["runner"] = "pier"

        validate_run_spec(self.spec)

    def test_audit_reports_derived_trajectory_count(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import json

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run-spec.json"
            path.write_text(json.dumps(self.spec))

            report = audit_run_spec(path)

        self.assertEqual(report["trajectory_count"], 4)
        self.assertTrue(report["run_spec_sha256"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

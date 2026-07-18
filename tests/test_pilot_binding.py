from __future__ import annotations

import unittest

from shallowswe.pilot_binding import (
    launch_matrix,
    resolve_launch_unit,
    resolve_model_config,
    resolve_trajectory,
)


class PilotBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.unit = {
            "launch_unit_id": "unit-1",
            "runner": "kaggle",
            "launch_status": "official_ready",
            "stage": "kaggle_canary",
            "model_role": "primary_anchor",
            "mode": "one_shot",
            "model": "model-snapshot",
            "model_config_id": "model-id",
            "agent_policy_id": "agent-id",
            "task_ids": ["task-a", "task-b"],
            "rollout_seeds_by_task": {"task-a": [0, 1], "task-b": [0, 1]},
            "trajectory_ids": ["trajectory-a0", "trajectory-a1", "trajectory-b0", "trajectory-b1"],
            "expected_trajectories": 4,
            "evidence_class": "official_pilot",
            "release_class": "protocol_validation",
        }
        self.schedule = {
            "rows": [
                {
                    "trajectory_id": f"trajectory-{task[-1]}{seed}",
                    "stage": "kaggle_canary",
                    "model_role": "primary_anchor",
                    "mode": "one_shot",
                    "task_id": task,
                    "rollout_seed": seed,
                    "model_config_id": "model-id",
                    "agent_policy_id": "agent-id",
                    "evidence_class": "official_pilot",
                    "release_class": "protocol_validation",
                }
                for task in ("task-a", "task-b")
                for seed in (0, 1)
            ]
        }

    def test_resolves_one_frozen_launch_row(self) -> None:
        unit = resolve_launch_unit({"units": [self.unit]}, "unit-1")
        self.assertEqual(launch_matrix(unit), (["task-a", "task-b"], [0, 1]))
        row = resolve_trajectory(
            unit,
            self.schedule,
            task_id="task-b",
            rollout_seed=1,
            model_config_id="model-id",
            requested_model="model-snapshot",
        )
        self.assertEqual(row["trajectory_id"], "trajectory-b1")

    def test_model_config_binding_preserves_same_model_effort_variants(self) -> None:
        configs = [
            {
                "model_config_id": "sol-high",
                "canonical": {"requested_model": "gpt-5.6-sol", "reasoning_effort": "high"},
            },
            {
                "model_config_id": "sol-low",
                "canonical": {"requested_model": "gpt-5.6-sol", "reasoning_effort": "low"},
            },
        ]

        selected = resolve_model_config(
            configs,
            requested_model="gpt-5.6-sol",
            model_config_id="sol-low",
        )

        self.assertEqual(selected["canonical"]["reasoning_effort"], "low")

    def test_rejects_unregistered_model_or_seed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "model"):
            resolve_trajectory(
                self.unit,
                self.schedule,
                task_id="task-a",
                rollout_seed=0,
                model_config_id="different-model",
                requested_model="model-snapshot",
            )

    def test_rejects_blocked_launch_unit(self) -> None:
        self.unit["launch_status"] = "blocked_by_pilot_readiness"

        with self.assertRaisesRegex(RuntimeError, "not launchable"):
            resolve_launch_unit({"units": [self.unit]}, "unit-1")

    def test_accepts_disjoint_contiguous_seed_namespace(self) -> None:
        self.unit["rollout_seeds_by_task"] = {
            "task-a": [4000, 4001],
            "task-b": [4000, 4001],
        }

        self.assertEqual(launch_matrix(self.unit), (["task-a", "task-b"], [4000, 4001]))
        with self.assertRaisesRegex(RuntimeError, "found 0"):
            resolve_trajectory(
                self.unit,
                self.schedule,
                task_id="task-a",
                rollout_seed=9,
                model_config_id="model-id",
                requested_model="model-snapshot",
            )

    def test_accepts_only_isolated_development_shadow_units(self) -> None:
        shadow = {
            "plan_class": "development_shadow",
            "units": [
                {
                    **self.unit,
                    "launch_status": "development_ready",
                    "evidence_class": "development_dry_run",
                    "release_class": "development_dry_run",
                }
            ],
        }

        self.assertEqual(resolve_launch_unit(shadow, "unit-1")["launch_unit_id"], "unit-1")

        shadow["units"][0]["release_class"] = "protocol_validation"
        with self.assertRaisesRegex(RuntimeError, "isolated"):
            resolve_launch_unit(shadow, "unit-1")

    def test_rejects_unknown_launch_plan_class(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "plan class"):
            resolve_launch_unit({"plan_class": "typo", "units": [self.unit]}, "unit-1")

    def test_rejects_schedule_row_with_different_evidence_boundary(self) -> None:
        self.schedule["rows"][0]["evidence_class"] = "development_dry_run"

        with self.assertRaisesRegex(RuntimeError, "found 0"):
            resolve_trajectory(
                self.unit,
                self.schedule,
                task_id="task-a",
                rollout_seed=0,
                model_config_id="model-id",
                requested_model="model-snapshot",
            )


if __name__ == "__main__":
    unittest.main()

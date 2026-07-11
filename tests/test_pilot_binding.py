from __future__ import annotations

import unittest

from shallowswe.pilot_binding import launch_matrix, resolve_launch_unit, resolve_trajectory


class PilotBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.unit = {
            "launch_unit_id": "unit-1",
            "runner": "kaggle",
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
        with self.assertRaisesRegex(RuntimeError, "found 0"):
            resolve_trajectory(
                self.unit,
                self.schedule,
                task_id="task-a",
                rollout_seed=9,
                model_config_id="model-id",
                requested_model="model-snapshot",
            )


if __name__ == "__main__":
    unittest.main()

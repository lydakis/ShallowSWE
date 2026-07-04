from __future__ import annotations

import unittest

from shallowswe.calibration import evaluate_one_shot_ceiling_gate, select_floor_pair
from shallowswe.results import row_from_mapping


def _row(
    *,
    model: str,
    task_id: str,
    size: str,
    rollout: int,
    passed: bool,
) -> dict[str, object]:
    return {
        "model": model,
        "task_id": task_id,
        "category": "code",
        "size": size,
        "rollout": rollout,
        "passed": passed,
        "input_tokens": 100,
        "output_tokens": 10,
        "turns": 1,
    }


class FloorSelectionTests(unittest.TestCase):
    def test_selects_non_saturated_pair_with_widest_task_spread(self) -> None:
        rows = [
            row_from_mapping(
                _row(
                    model="steady",
                    task_id="small-a",
                    size="small",
                    rollout=0,
                    passed=True,
                )
            ),
            row_from_mapping(
                _row(
                    model="steady",
                    task_id="small-a",
                    size="small",
                    rollout=1,
                    passed=False,
                )
            ),
            row_from_mapping(
                _row(
                    model="steady",
                    task_id="large-a",
                    size="large",
                    rollout=0,
                    passed=True,
                )
            ),
            row_from_mapping(
                _row(
                    model="steady",
                    task_id="large-a",
                    size="large",
                    rollout=1,
                    passed=False,
                )
            ),
            row_from_mapping(
                _row(
                    model="spread",
                    task_id="small-a",
                    size="small",
                    rollout=0,
                    passed=True,
                )
            ),
            row_from_mapping(
                _row(
                    model="spread",
                    task_id="small-a",
                    size="small",
                    rollout=1,
                    passed=True,
                )
            ),
            row_from_mapping(
                _row(
                    model="spread",
                    task_id="large-a",
                    size="large",
                    rollout=0,
                    passed=False,
                )
            ),
            row_from_mapping(
                _row(
                    model="spread",
                    task_id="large-a",
                    size="large",
                    rollout=1,
                    passed=False,
                )
            ),
            row_from_mapping(
                _row(
                    model="saturated",
                    task_id="small-a",
                    size="small",
                    rollout=0,
                    passed=True,
                )
            ),
            row_from_mapping(
                _row(
                    model="saturated",
                    task_id="large-a",
                    size="large",
                    rollout=0,
                    passed=True,
                )
            ),
        ]

        report = select_floor_pair(rows, saturation_threshold=0.85)
        candidates = {row["model_config"]: row for row in report["candidates"]}

        self.assertEqual(report["recommended_floor_model_config"], "spread")
        self.assertFalse(candidates["saturated"]["floor_candidate"])
        self.assertAlmostEqual(candidates["spread"]["task_pass_rate_range"], 1.0)
        self.assertEqual(candidates["spread"]["large_band_task_count"], 1)
        self.assertAlmostEqual(candidates["spread"]["size_pass_rates"]["large"], 0.0)

    def test_rejects_invalid_saturation_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "saturation_threshold"):
            select_floor_pair([], saturation_threshold=0)


class OneShotCeilingGateTests(unittest.TestCase):
    def test_applies_pre_registered_ceiling_gate_by_task(self) -> None:
        rows = [
            *[
                row_from_mapping(
                    _row(
                        model="ceiling",
                        task_id="accepted",
                        size="small",
                        rollout=rollout,
                        passed=rollout < 3,
                    )
                )
                for rollout in range(4)
            ],
            *[
                row_from_mapping(
                    _row(
                        model="ceiling",
                        task_id="investigate",
                        size="medium",
                        rollout=rollout,
                        passed=rollout < 2,
                    )
                )
                for rollout in range(4)
            ],
            *[
                row_from_mapping(
                    _row(
                        model="ceiling",
                        task_id="fix",
                        size="large",
                        rollout=rollout,
                        passed=rollout == 0,
                    )
                )
                for rollout in range(4)
            ],
            row_from_mapping(
                _row(
                    model="ceiling",
                    task_id="smoke-only",
                    size="small",
                    rollout=0,
                    passed=True,
                )
            ),
        ]

        report = evaluate_one_shot_ceiling_gate(
            rows,
            pass_threshold=0.75,
            target_rollouts=4,
        )
        tasks = {row["task_id"]: row for row in report["tasks"]}

        self.assertEqual(report["accept_min_passes"], 3)
        self.assertEqual(report["investigate_min_passes"], 2)
        self.assertEqual(tasks["accepted"]["decision"], "accept")
        self.assertEqual(tasks["investigate"]["decision"], "investigate")
        self.assertEqual(tasks["fix"]["decision"], "fix_or_evict")
        self.assertEqual(tasks["smoke-only"]["decision"], "needs_more_rollouts")
        self.assertEqual(tasks["smoke-only"]["missing_rollouts"], 3)

        summary = report["model_summaries"][0]
        self.assertFalse(summary["clears_gate"])
        self.assertEqual(
            summary["decision_counts"],
            {
                "accept": 1,
                "fix_or_evict": 1,
                "investigate": 1,
                "needs_more_rollouts": 1,
            },
        )

    def test_rejects_invalid_ceiling_gate_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "pass_threshold"):
            evaluate_one_shot_ceiling_gate([], pass_threshold=0)
        with self.assertRaisesRegex(ValueError, "target_rollouts"):
            evaluate_one_shot_ceiling_gate([], target_rollouts=0)


if __name__ == "__main__":
    unittest.main()

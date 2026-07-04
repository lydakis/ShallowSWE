from __future__ import annotations

import unittest

from shallowswe.results import ModelPrice, row_from_mapping
from shallowswe.workload import build_workload_index


def _row(
    *,
    model: str,
    task_id: str,
    category: str,
    tier: str,
    input_tokens: int,
    reasoning_effort: str | None = None,
    rollout: int = 0,
    passed: bool = True,
) -> dict[str, object]:
    row: dict[str, object] = {
        "model": model,
        "task_id": task_id,
        "category": category,
        "tier": tier,
        "rollout": rollout,
        "passed": passed,
        "input_tokens": input_tokens,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "turns": 1,
    }
    if reasoning_effort:
        row["reasoning_effort"] = reasoning_effort
    return row


class WorkloadIndexTests(unittest.TestCase):
    def test_default_index_equalizes_categories_tiers_and_observed_tasks(self) -> None:
        prices = {
            "model": ModelPrice(
                input_per_1m=1.0,
                cached_input_per_1m=None,
                output_per_1m=0.0,
            )
        }
        rows = [
            row_from_mapping(
                _row(
                    model="model",
                    task_id="fix-a",
                    category="fix",
                    tier="t1",
                    input_tokens=1_000_000,
                )
            ),
            row_from_mapping(
                _row(
                    model="model",
                    task_id="fix-b",
                    category="fix",
                    tier="t1",
                    input_tokens=3_000_000,
                )
            ),
            row_from_mapping(
                _row(
                    model="model",
                    task_id="transform-a",
                    category="transform",
                    tier="t1",
                    input_tokens=100_000_000,
                )
            ),
        ]

        index = build_workload_index(rows, prices=prices)
        model = index["models"][0]

        self.assertEqual(model["model_config"], "model")
        self.assertEqual(index["weighting"]["target_tasks_per_category_size"], 4)
        self.assertAlmostEqual(model["basket_cpsc"], 51.0)
        self.assertEqual(model["rank_by_basket_cpsc"], 1)
        weights = {
            task["task_id"]: task["default_weight"]
            for task in index["task_weights"]
        }
        self.assertAlmostEqual(weights["fix-a"], 0.25)
        self.assertAlmostEqual(weights["fix-b"], 0.25)
        self.assertAlmostEqual(weights["transform-a"], 0.5)

    def test_missing_model_cells_make_official_basket_null_but_partial_available(self) -> None:
        prices = {
            "complete": ModelPrice(1.0, None, 0.0),
            "partial": ModelPrice(1.0, None, 0.0),
        }
        rows = [
            row_from_mapping(
                _row(
                    model="complete",
                    task_id="fix-a",
                    category="fix",
                    tier="t1",
                    input_tokens=1_000_000,
                )
            ),
            row_from_mapping(
                _row(
                    model="complete",
                    task_id="transform-a",
                    category="transform",
                    tier="t1",
                    input_tokens=3_000_000,
                )
            ),
            row_from_mapping(
                _row(
                    model="partial",
                    task_id="fix-a",
                    category="fix",
                    tier="t1",
                    input_tokens=2_000_000,
                )
            ),
        ]

        index = build_workload_index(rows, prices=prices)
        by_model = {model["model_config"]: model for model in index["models"]}

        self.assertIsNone(by_model["partial"]["basket_cpsc"])
        self.assertAlmostEqual(by_model["partial"]["partial_basket_cpsc"], 2.0)
        self.assertAlmostEqual(by_model["partial"]["covered_weight"], 0.5)
        self.assertAlmostEqual(by_model["partial"]["missing_weight"], 0.5)

    def test_reasoning_effort_creates_distinct_model_config(self) -> None:
        prices = {"model": ModelPrice(1.0, None, 0.0)}
        rows = [
            row_from_mapping(
                _row(
                    model="model",
                    task_id="fix-a",
                    category="fix",
                    tier="t1",
                    input_tokens=1_000_000,
                    reasoning_effort="low",
                )
            ),
            row_from_mapping(
                _row(
                    model="model",
                    task_id="fix-a",
                    category="fix",
                    tier="t1",
                    input_tokens=2_000_000,
                    reasoning_effort="high",
                )
            ),
        ]

        index = build_workload_index(rows, prices=prices)
        configs = {model["model_config"] for model in index["models"]}

        self.assertEqual(configs, {"model[low]", "model[high]"})

    def test_legacy_t4_rows_enter_default_basket_as_large(self) -> None:
        prices = {"model": ModelPrice(1.0, None, 0.0)}
        rows = [
            row_from_mapping(
                _row(
                    model="model",
                    task_id="fix-a",
                    category="fix",
                    tier="t1",
                    input_tokens=1_000_000,
                )
            ),
            row_from_mapping(
                _row(
                    model="model",
                    task_id="fix-edge",
                    category="fix",
                    tier="t4",
                    input_tokens=100_000_000,
                )
            ),
        ]

        index = build_workload_index(rows, prices=prices)
        model = index["models"][0]

        self.assertAlmostEqual(model["basket_cpsc"], 50.5)
        self.assertEqual([task["task_id"] for task in index["task_weights"]], ["fix-a", "fix-edge"])
        self.assertEqual([cell["task_id"] for cell in index["cells"]], ["fix-a", "fix-edge"])
        self.assertEqual(index["weighting"]["included_sizes"], ["small", "medium", "large"])

    def test_zero_success_task_contributes_to_basket_retry_tax(self) -> None:
        prices = {"model": ModelPrice(1.0, None, 0.0)}
        failed = _row(
            model="model",
            task_id="invoke-edge",
            category="invoke",
            tier="t4",
            input_tokens=3_000_000,
        )
        failed["passed"] = False
        rows = [
            row_from_mapping(
                _row(
                    model="model",
                    task_id="fix-a",
                    category="fix",
                    tier="t1",
                    input_tokens=1_000_000,
                )
            ),
            row_from_mapping(failed),
        ]

        index = build_workload_index(rows, prices=prices)
        model = index["models"][0]

        self.assertAlmostEqual(model["weighted_pass_rate"], 0.5)
        self.assertAlmostEqual(model["weighted_mean_cost_per_attempt"], 2.0)
        self.assertAlmostEqual(model["basket_cpsc"], 4.0)


if __name__ == "__main__":
    unittest.main()

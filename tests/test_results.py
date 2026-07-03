from __future__ import annotations

import unittest

from shallowswe.results import aggregate_results, row_from_mapping


class ResultAggregationTests(unittest.TestCase):
    def test_cpsc_includes_retry_tax_without_double_counting_cache(self) -> None:
        rows = [
            row_from_mapping(
                {
                    "model": "small",
                    "task_id": "example",
                    "category": "fix",
                    "tier": "t1",
                    "rollout": 0,
                    "passed": True,
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_tokens": 25,
                    "cost_usd": 0.001,
                    "turns": 1,
                }
            ),
            row_from_mapping(
                {
                    "model": "small",
                    "task_id": "example",
                    "category": "fix",
                    "tier": "t1",
                    "rollout": 1,
                    "passed": False,
                    "input_tokens": 300,
                    "output_tokens": 80,
                    "cache_tokens": 100,
                    "cost_usd": 0.003,
                    "turns": 4,
                }
            ),
        ]

        summary = aggregate_results(rows)[0]

        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertAlmostEqual(summary["mean_cost_per_attempt"], 0.002)
        self.assertAlmostEqual(summary["cpsc"], 0.004)
        self.assertAlmostEqual(summary["mean_tokens_per_attempt"], 250.0)
        self.assertAlmostEqual(summary["tokens_per_success"], 500.0)

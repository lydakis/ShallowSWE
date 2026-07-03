from __future__ import annotations

import unittest

from shallowswe.results import ModelPrice, aggregate_results, row_from_mapping


class ResultAggregationTests(unittest.TestCase):
    def test_cpsc_includes_retry_tax_without_double_counting_cache(self) -> None:
        prices = {
            "small": ModelPrice(
                input_per_1m=10.0,
                cached_input_per_1m=2.0,
                output_per_1m=100.0,
            )
        }
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
                    "cache_read_tokens": 25,
                    "peak_context_tokens": 100,
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
                    "cache_read_tokens": 100,
                    "peak_context_tokens": 300,
                    "turns": 4,
                }
            ),
        ]

        summary = aggregate_results(rows, prices=prices)[0]

        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertAlmostEqual(summary["mean_cost_per_attempt"], 0.0065)
        self.assertAlmostEqual(summary["cpsc"], 0.013)
        self.assertAlmostEqual(summary["mean_tokens_per_attempt"], 250.0)
        self.assertAlmostEqual(summary["tokens_per_success"], 500.0)

    def test_cost_uses_long_context_rates_when_peak_context_crosses_threshold(self) -> None:
        prices = {
            "model": ModelPrice(
                input_per_1m=1.0,
                cached_input_per_1m=0.5,
                output_per_1m=10.0,
                long_context_threshold_tokens=100,
                long_context_input_per_1m=2.0,
                long_context_cached_input_per_1m=1.0,
                long_context_output_per_1m=15.0,
            )
        }
        rows = [
            row_from_mapping(
                {
                    "model": "model",
                    "task_id": "example",
                    "category": "fix",
                    "tier": "t1",
                    "rollout": 0,
                    "passed": True,
                    "input_tokens": 200,
                    "output_tokens": 10,
                    "cache_read_tokens": 50,
                    "peak_context_tokens": 101,
                    "turns": 1,
                }
            )
        ]

        summary = aggregate_results(rows, prices=prices)[0]

        self.assertAlmostEqual(summary["mean_cost_per_attempt"], 0.0005)

    def test_aggregate_without_prices_reports_token_metrics_only(self) -> None:
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
                    "cache_read_tokens": 25,
                    "turns": 1,
                }
            )
        ]

        summary = aggregate_results(rows)[0]

        self.assertNotIn("mean_cost_per_attempt", summary)
        self.assertNotIn("cpsc", summary)
        self.assertEqual(summary["tokens_per_success"], 120)

    def test_excluded_rows_do_not_pollute_scored_attempts(self) -> None:
        prices = {
            "small": ModelPrice(
                input_per_1m=10.0,
                cached_input_per_1m=2.0,
                output_per_1m=100.0,
            )
        }
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
                    "cache_read_tokens": 25,
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
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_tokens": 0,
                    "turns": 0,
                    "status": "excluded",
                    "exclusion_reason": "provider_or_network_error",
                }
            ),
        ]

        summary = aggregate_results(rows, prices=prices)[0]

        self.assertEqual(summary["total_trials"], 2)
        self.assertEqual(summary["attempts"], 1)
        self.assertEqual(summary["excluded_attempts"], 1)
        self.assertEqual(summary["pass_rate"], 1.0)
        self.assertAlmostEqual(summary["mean_cost_per_attempt"], 0.0028)

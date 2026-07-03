from __future__ import annotations

import unittest

from shallowswe.results import ModelPrice, aggregate_results, rollout_cost_usd, row_from_mapping


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
                    "reasoning_tokens": 5,
                    "peak_context_tokens": 100,
                    "turns": 1,
                    "gateway_reported_cost_usd": 0.0028,
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
                    "cache_write_tokens": 50,
                    "reasoning_tokens": 10,
                    "peak_context_tokens": 300,
                    "turns": 4,
                    "gateway_reported_cost_usd": 0.0104,
                }
            ),
        ]

        summary = aggregate_results(rows, prices=prices)[0]

        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertAlmostEqual(summary["mean_cost_per_attempt"], 0.0065)
        self.assertAlmostEqual(summary["cpsc"], 0.013)
        self.assertAlmostEqual(summary["mean_tokens_per_attempt"], 250.0)
        self.assertAlmostEqual(summary["tokens_per_success"], 500.0)
        self.assertAlmostEqual(summary["mean_input_tokens_per_attempt"], 200.0)
        self.assertAlmostEqual(summary["mean_output_tokens_per_attempt"], 50.0)
        self.assertAlmostEqual(summary["mean_cache_read_tokens_per_attempt"], 62.5)
        self.assertAlmostEqual(summary["mean_cache_write_tokens_per_attempt"], 25.0)
        self.assertAlmostEqual(summary["mean_reasoning_tokens_per_attempt"], 7.5)
        self.assertEqual(summary["gateway_reported_attempts"], 2)
        self.assertAlmostEqual(
            summary["mean_gateway_reported_cost_per_attempt"],
            0.0066,
        )
        self.assertAlmostEqual(
            summary["mean_cost_delta_vs_gateway_per_attempt"],
            -0.0001,
        )
        self.assertAlmostEqual(
            summary["cost_delta_vs_gateway_ratio"],
            -0.0002 / 0.0132,
        )

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

    def test_default_aggregate_separates_reasoning_effort_configs(self) -> None:
        rows = [
            row_from_mapping(
                {
                    "model": "model",
                    "task_id": "example",
                    "category": "fix",
                    "tier": "t1",
                    "rollout": 0,
                    "passed": True,
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_tokens": 0,
                    "turns": 1,
                    "reasoning_effort": "low",
                }
            ),
            row_from_mapping(
                {
                    "model": "model",
                    "task_id": "example",
                    "category": "fix",
                    "tier": "t1",
                    "rollout": 0,
                    "passed": True,
                    "input_tokens": 200,
                    "output_tokens": 20,
                    "cache_read_tokens": 0,
                    "turns": 1,
                    "reasoning_effort": "high",
                }
            ),
        ]

        summaries = aggregate_results(rows)

        self.assertEqual(
            {summary["model_config"] for summary in summaries},
            {"model[low]", "model[high]"},
        )

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

    def test_gateway_reported_cost_can_be_reconciled_with_price_sheet(self) -> None:
        prices = {
            "google/gemini-3.5-flash": ModelPrice(
                input_per_1m=1.5,
                cached_input_per_1m=0.15,
                output_per_1m=9.0,
                cache_write_per_1m=0.08333333333333334,
            )
        }
        row = row_from_mapping(
            {
                "model": "google/gemini-3.5-flash",
                "task_id": "py-normalize-username",
                "category": "fix",
                "tier": "t1",
                "rollout": 0,
                "passed": True,
                "input_tokens": 10473,
                "output_tokens": 899,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "turns": 8,
                "gateway_reported_cost_usd": 0.023800500000000002,
            }
        )

        self.assertAlmostEqual(
            rollout_cost_usd(row, prices),
            row.gateway_reported_cost_usd,
        )

    def test_poolside_smoke_cost_reconciles_cache_reads(self) -> None:
        prices = {
            "poolside/laguna-xs-2.1": ModelPrice(
                input_per_1m=0.06,
                cached_input_per_1m=0.03,
                output_per_1m=0.12,
                provider="poolside",
                gateway="openrouter",
            )
        }
        row = row_from_mapping(
            {
                "model": "poolside/laguna-xs-2.1",
                "task_id": "py-normalize-username",
                "category": "fix",
                "tier": "t1",
                "rollout": 0,
                "passed": True,
                "input_tokens": 18893,
                "output_tokens": 1312,
                "cache_read_tokens": 9904,
                "cache_write_tokens": 0,
                "turns": 9,
                "inference_gateway": "openrouter",
                "gateway_reported_cost_usd": 0.0009938999999999998,
            }
        )

        self.assertAlmostEqual(
            rollout_cost_usd(row, prices),
            row.gateway_reported_cost_usd,
        )

    def test_direct_provider_price_does_not_match_gateway_row(self) -> None:
        prices = {
            "openai/gpt-5.5": ModelPrice(
                input_per_1m=5.0,
                cached_input_per_1m=0.5,
                output_per_1m=30.0,
                provider="openai",
                gateway="openai",
            )
        }
        row = row_from_mapping(
            {
                "model": "openai/gpt-5.5",
                "task_id": "example",
                "category": "fix",
                "tier": "t1",
                "rollout": 0,
                "passed": True,
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_tokens": 0,
                "turns": 1,
                "inference_gateway": "openrouter",
            }
        )

        with self.assertRaisesRegex(ValueError, "no price found"):
            rollout_cost_usd(row, prices)

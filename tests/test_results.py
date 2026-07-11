from __future__ import annotations

from pathlib import Path
import json
import unittest

from shallowswe.results import (
    ModelPrice,
    REPAIR_LOOP_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    aggregate_repair_loops,
    aggregate_results,
    load_results,
    merge_prices,
    repair_loop_from_mapping,
    rollout_cost_usd,
    row_from_mapping,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResultExampleTests(unittest.TestCase):
    def test_sample_result_uses_current_public_schema(self) -> None:
        path = REPO_ROOT / "examples" / "results.sample.json"
        raw_rows = json.loads(path.read_text())

        self.assertTrue(raw_rows)
        for row in raw_rows:
            self.assertEqual(row["schema_version"], RESULT_SCHEMA_VERSION)
            self.assertIn("size", row)
            self.assertNotIn("tier", row)

        rows = load_results(path)
        self.assertEqual(rows[0].category, "code")
        self.assertEqual(rows[0].size, "small")


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

    def test_repair_loop_cpsc_counts_failed_cap_spend(self) -> None:
        prices = {
            "small": ModelPrice(
                input_per_1m=1.0,
                cached_input_per_1m=None,
                output_per_1m=1.0,
            )
        }
        rows = [
            repair_loop_from_mapping(
                {
                    "schema_version": REPAIR_LOOP_SCHEMA_VERSION,
                    "model": "small",
                    "task_id": "example",
                    "category": "code",
                    "size": "small",
                    "loop": 0,
                    "passed": True,
                    "stop_reason": "passed",
                    "verifier_submissions": 1,
                    "input_tokens": 1_000_000,
                    "output_tokens": 0,
                    "turns": 2,
                    "agent_steps": 4,
                }
            ),
            repair_loop_from_mapping(
                {
                    "schema_version": REPAIR_LOOP_SCHEMA_VERSION,
                    "model": "small",
                    "task_id": "example",
                    "category": "code",
                    "size": "small",
                    "loop": 1,
                    "passed": True,
                    "stop_reason": "passed",
                    "verifier_submissions": 3,
                    "input_tokens": 3_000_000,
                    "output_tokens": 0,
                    "turns": 6,
                    "agent_steps": 12,
                }
            ),
            repair_loop_from_mapping(
                {
                    "schema_version": REPAIR_LOOP_SCHEMA_VERSION,
                    "model": "small",
                    "task_id": "example",
                    "category": "code",
                    "size": "small",
                    "loop": 2,
                    "passed": False,
                    "stop_reason": "submission_cap",
                    "verifier_submissions": 5,
                    "input_tokens": 2_000_000,
                    "output_tokens": 0,
                    "turns": 8,
                    "agent_steps": 20,
                }
            ),
            repair_loop_from_mapping(
                {
                    "schema_version": REPAIR_LOOP_SCHEMA_VERSION,
                    "model": "small",
                    "task_id": "example",
                    "category": "code",
                    "size": "small",
                    "loop": 4,
                    "passed": False,
                    "stop_reason": "agent_step_cap",
                    "verifier_submissions": 2,
                    "input_tokens": 1_000_000,
                    "output_tokens": 0,
                    "turns": 20,
                    "agent_steps": 20,
                }
            ),
            repair_loop_from_mapping(
                {
                    "schema_version": REPAIR_LOOP_SCHEMA_VERSION,
                    "model": "small",
                    "task_id": "example",
                    "category": "code",
                    "size": "small",
                    "loop": 3,
                    "passed": False,
                    "stop_reason": "wall_time_cap",
                    "verifier_submissions": 0,
                    "input_tokens": 9_000_000,
                    "output_tokens": 0,
                    "turns": 0,
                    "status": "excluded",
                    "exclusion_reason": "infra_wall_time_guard",
                }
            ),
        ]

        summary = aggregate_repair_loops(rows, prices=prices)[0]

        self.assertEqual(summary["repair_loops"], 4)
        self.assertEqual(summary["excluded_repair_loops"], 1)
        self.assertEqual(summary["successes"], 2)
        self.assertAlmostEqual(summary["solve_rate"], 2 / 4)
        self.assertEqual(summary["cap_hits"], 2)
        self.assertAlmostEqual(summary["cap_hit_rate"], 2 / 4)
        self.assertAlmostEqual(summary["total_model_spend_usd"], 7.0)
        self.assertAlmostEqual(summary["mean_cost_per_repair_loop"], 7.0 / 4)
        self.assertAlmostEqual(summary["p95_cost_per_repair_loop"], 3.0)
        self.assertAlmostEqual(summary["cpsc"], 3.5)
        self.assertAlmostEqual(summary["conditional_spend_among_solved_loops"], 2.0)
        self.assertAlmostEqual(summary["mean_spend_per_solved_task"], 2.0)
        self.assertAlmostEqual(summary["conditional_tokens_among_solved_loops"], 2_000_000.0)
        self.assertAlmostEqual(summary["p95_turns_per_repair_loop"], 20.0)
        self.assertAlmostEqual(summary["p95_agent_steps_per_repair_loop"], 20.0)
        self.assertAlmostEqual(summary["mean_verifier_submissions_to_success"], 2.0)
        self.assertEqual(
            summary["stop_reasons"],
            {"passed": 2, "submission_cap": 1, "agent_step_cap": 1},
        )

    def test_repair_loop_rows_preserve_public_snapshot_provenance(self) -> None:
        row = repair_loop_from_mapping(
            {
                "schema_version": REPAIR_LOOP_SCHEMA_VERSION,
                "model": "small",
                "task_id": "example",
                "category": "code",
                "size": "small",
                "loop": 0,
                "passed": True,
                "stop_reason": "passed",
                "verifier_submissions": 1,
                "input_tokens": 100,
                "output_tokens": 20,
                "turns": 2,
                "task_version": "example@v1",
                "task_suite_version": "shallowswe-v1",
                "verifier_hash": "sha256:verifier",
                "environment_image_digest": "sha256:image",
                "repo_commit_sha": "abc123",
                "price_sheet_version": "openrouter-2026-07-03",
                "price_sheet_date": "2026-07-03",
                "seed": 42,
                "run_id": "run-1",
                "task_visibility": "public",
                "transcript_hash": "sha256:transcript",
            }
        )

        self.assertEqual(row.task_version, "example@v1")
        self.assertEqual(row.task_suite_version, "shallowswe-v1")
        self.assertEqual(row.verifier_hash, "sha256:verifier")
        self.assertEqual(row.environment_image_digest, "sha256:image")
        self.assertEqual(row.repo_commit_sha, "abc123")
        self.assertEqual(row.price_sheet_version, "openrouter-2026-07-03")
        self.assertEqual(row.price_sheet_date, "2026-07-03")
        self.assertEqual(row.seed, 42)
        self.assertEqual(row.run_id, "run-1")
        self.assertEqual(row.task_visibility, "public")
        self.assertEqual(row.transcript_hash, "sha256:transcript")

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

    def test_merged_prices_preserve_gateway_specific_duplicate_aliases(self) -> None:
        prices = merge_prices(
            {
                "openai/gpt-5.5": ModelPrice(
                    input_per_1m=1.0,
                    cached_input_per_1m=None,
                    output_per_1m=10.0,
                    provider="openai",
                    gateway="openrouter",
                )
            },
            {
                "openai/gpt-5.5": ModelPrice(
                    input_per_1m=100.0,
                    cached_input_per_1m=None,
                    output_per_1m=10.0,
                    provider="openai",
                    gateway="openai",
                )
            },
        )
        openrouter_row = row_from_mapping(
            {
                "model": "openai/gpt-5.5",
                "task_id": "example",
                "category": "fix",
                "tier": "t1",
                "rollout": 0,
                "passed": True,
                "input_tokens": 1_000_000,
                "output_tokens": 0,
                "turns": 1,
                "inference_gateway": "openrouter",
            }
        )
        direct_row = row_from_mapping(
            {
                "model": "openai/gpt-5.5",
                "task_id": "example",
                "category": "fix",
                "tier": "t1",
                "rollout": 0,
                "passed": True,
                "input_tokens": 1_000_000,
                "output_tokens": 0,
                "turns": 1,
                "inference_gateway": "openai",
            }
        )

        self.assertAlmostEqual(rollout_cost_usd(openrouter_row, prices), 1.0)
        self.assertAlmostEqual(rollout_cost_usd(direct_row, prices), 100.0)

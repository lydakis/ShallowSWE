from __future__ import annotations

import math
import json
from pathlib import Path
import unittest

from scripts.analyze_kimi_k3_article_followup import (
    pearson,
    rankdata,
    residualize,
    spend_decomposition,
    summarize_cache_rows,
    summarize_retry_task,
)


class KimiK3ArticleFollowupTests(unittest.TestCase):
    def test_checked_in_spec_is_existing_data_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        spec = json.loads(
            (root / "configs/analyses/kimi-k3-article-followup-2026-07-19/spec.json").read_text()
        )
        self.assertEqual(spec["status"], "existing_data_only_no_runs_authorized")
        self.assertTrue(spec["claim_boundary"]["no_paid_run_authorization"])
        self.assertEqual(
            spec["lineage"]["primary_variant"],
            "focal_complete_raw_focal_shared",
        )

    def test_rankdata_averages_ties(self) -> None:
        self.assertEqual(rankdata([1.0, 1.0, 3.0, 2.0]), [1.5, 1.5, 4.0, 3.0])

    def test_residualize_removes_linear_control(self) -> None:
        values = [1.0, 4.0, 7.0, 10.0]
        control = [0.0, 1.0, 2.0, 3.0]
        residuals = residualize(values, control)
        self.assertTrue(all(abs(value) < 1e-12 for value in residuals))

    def test_pearson_handles_a_perfect_relationship(self) -> None:
        self.assertAlmostEqual(pearson([0.0, 1.0, 2.0], [0.0, 2.0, 4.0]), 1.0)

    def test_retry_summary_averages_order_without_replacement(self) -> None:
        rows = [
            {"trial_name": "a", "passed": False, "cost_usd": 1.0},
            {"trial_name": "b", "passed": True, "cost_usd": 2.0},
            {"trial_name": "c", "passed": False, "cost_usd": 3.0},
            {"trial_name": "d", "passed": True, "cost_usd": 4.0},
        ]
        summary = summarize_retry_task(rows, attempts=2)
        self.assertAlmostEqual(summary["coverage"], 5 / 6)
        self.assertAlmostEqual(summary["stopped_cost_usd"], 23 / 6)

    def test_spend_decomposition_adds_back_to_realized_cpsc(self) -> None:
        rows = [
            {"passed": False, "cost_usd": 1.0},
            {"passed": True, "cost_usd": 2.0},
            {"passed": False, "cost_usd": 3.0},
            {"passed": True, "cost_usd": 4.0},
        ]
        result = spend_decomposition(rows)
        self.assertAlmostEqual(result["pass_rate"], 0.5)
        self.assertAlmostEqual(result["mean_success_cost_usd"], 3.0)
        self.assertAlmostEqual(result["realized_reliability_tax_usd"], 2.0)
        self.assertAlmostEqual(result["realized_cpsc_usd"], 5.0)

    def test_cache_summary_uses_token_weighting_and_fixed_bins(self) -> None:
        rows = [
            {"task_id": "a", "agent_steps": 5, "input_tokens": 100, "cache_read_tokens": 50},
            {"task_id": "b", "agent_steps": 20, "input_tokens": 200, "cache_read_tokens": 180},
            {"task_id": "c", "agent_steps": 60, "input_tokens": 300, "cache_read_tokens": 294},
        ]
        result = summarize_cache_rows(rows, [(1, 9), (10, 24), (25, 49), (50, None)])
        self.assertAlmostEqual(result["token_weighted_cache_share"], 524 / 600)
        self.assertAlmostEqual(result["median_attempt_cache_share"], 0.9)
        self.assertEqual([row["attempts"] for row in result["step_bins"]], [1, 1, 0, 1])
        self.assertTrue(math.isnan(result["step_bins"][2]["token_weighted_cache_share"]))


if __name__ == "__main__":
    unittest.main()

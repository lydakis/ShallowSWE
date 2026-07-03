from __future__ import annotations

import unittest

from shallowswe.deepswe import build_deepswe_comparison


class DeepSWEComparisonTests(unittest.TestCase):
    def test_comparison_matches_provider_prefixed_model_names(self) -> None:
        workload_index = {
            "schema_version": "shallowswe.workload_index.v0.1",
            "models": [
                {
                    "model_config": "moonshotai/kimi-k2.7-code",
                    "model": "moonshotai/kimi-k2.7-code",
                    "reasoning_effort": None,
                    "basket_cpsc": 0.0037,
                    "partial_basket_cpsc": 0.0037,
                    "basket_tokens_per_success": 6694.0,
                    "covered_weight": 1.0,
                }
            ],
        }
        deepswe = {
            "generated_at": "2026-07-03T00:00:00Z",
            "rows": [
                {
                    "model": "kimi-k2-7-code",
                    "config": "mini_swe_agent_kimi_k2_7_code_default",
                    "reasoning_effort": "default",
                    "pass_rate": 0.305,
                    "mean_cost_usd": 2.82,
                    "mean_input_tokens": 13_008_041,
                    "mean_output_tokens": 59_297,
                }
            ],
        }

        comparison = build_deepswe_comparison(workload_index, deepswe)
        row = comparison["rows"][0]

        self.assertEqual(row["model_config"], "moonshotai/kimi-k2.7-code")
        self.assertEqual(row["deepswe_model"], "kimi-k2-7-code")
        self.assertAlmostEqual(row["deepswe_cpsc"], 2.82 / 0.305)
        self.assertAlmostEqual(row["shallowswe_basket_cpsc"], 0.0037)


if __name__ == "__main__":
    unittest.main()

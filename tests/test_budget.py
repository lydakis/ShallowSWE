from __future__ import annotations

from pathlib import Path
import unittest

from shallowswe.budget import TokenBasis, estimate_panel_budget, load_panel
from shallowswe.results import ModelPrice, load_prices


REPO_ROOT = Path(__file__).resolve().parents[1]


class PanelBudgetTests(unittest.TestCase):
    def test_estimate_prices_known_rows_and_reports_missing_rows(self) -> None:
        panel = {
            "name": "test-panel",
            "status": "seed",
            "defaults": {"inference_gateway": "openrouter"},
            "rows": [
                {
                    "id": "gemini_flash_medium",
                    "model": "gemini-flash",
                    "openrouter_model": "google/gemini-3.5-flash",
                    "upstream_provider": "google",
                    "reasoning_effort": "medium",
                },
                {
                    "id": "missing_model",
                    "model": "missing",
                    "openrouter_model": "missing/model",
                    "upstream_provider": "example",
                    "reasoning_effort": None,
                },
            ],
        }
        prices = {
            "google/gemini-3.5-flash": ModelPrice(
                input_per_1m=1.5,
                cached_input_per_1m=0.15,
                output_per_1m=9.0,
                cache_write_per_1m=0.08333333333333334,
            )
        }

        estimate = estimate_panel_budget(
            panel,
            prices,
            task_count=2,
            rollouts_per_task=3,
            token_basis=TokenBasis(input_tokens=10_473, output_tokens=899),
        )

        self.assertEqual(estimate["rows"], 2)
        self.assertEqual(estimate["priced_rows"], 1)
        self.assertEqual(estimate["missing_price_rows"], 1)
        self.assertEqual(estimate["estimated_attempts_per_row"], 6)
        self.assertAlmostEqual(estimate["priced_subset_cost_usd"], 0.0238005 * 6)
        self.assertIsNone(estimate["estimated_full_panel_cost_usd"])
        self.assertEqual(estimate["missing_prices"][0]["id"], "missing_model")

    def test_rejects_cache_tokens_above_input_tokens(self) -> None:
        panel = {"rows": [{"id": "row", "model": "model"}]}
        prices = {
            "model": ModelPrice(
                input_per_1m=1.0,
                cached_input_per_1m=0.1,
                output_per_1m=5.0,
            )
        }

        with self.assertRaisesRegex(ValueError, "cache tokens cannot exceed input tokens"):
            estimate_panel_budget(
                panel,
                prices,
                task_count=1,
                rollouts_per_task=1,
                token_basis=TokenBasis(
                    input_tokens=10,
                    output_tokens=1,
                    cache_read_tokens=11,
                ),
            )

    def test_seed_panel_resolves_against_openrouter_price_sheet(self) -> None:
        estimate = estimate_panel_budget(
            load_panel(REPO_ROOT / "panels" / "deepswe-v1.1-seed.json"),
            load_prices(REPO_ROOT / "prices" / "openrouter-2026-07-03.json"),
            task_count=1,
            rollouts_per_task=1,
            token_basis=TokenBasis(),
        )

        self.assertEqual(estimate["rows"], 26)
        self.assertEqual(estimate["priced_rows"], 26)
        self.assertEqual(estimate["missing_price_rows"], 0)
        self.assertIsNotNone(estimate["estimated_full_panel_cost_usd"])

    def test_medium_preview_panel_is_priced_and_keeps_kimi_default_explicit(self) -> None:
        panel = load_panel(REPO_ROOT / "panels" / "deepswe-v1.1-medium-preview.json")
        rows = panel["rows"]
        ids = {row["id"] for row in rows}

        self.assertEqual(
            ids,
            {
                "mini_swe_agent_gpt_5_5_medium",
                "mini_swe_agent_claude_opus_4_8_medium",
                "mini_swe_agent_claude_sonnet_5_medium",
                "mini_swe_agent_gemini_3_5_flash_medium",
                "mini_swe_agent_kimi_k2_7_code_default",
            },
        )
        self.assertFalse(any("fable" in row["id"] for row in rows))
        self.assertFalse(any("laguna" in row["id"] for row in rows))
        for row in rows:
            if row["id"] == "mini_swe_agent_kimi_k2_7_code_default":
                self.assertIsNone(row["reasoning_effort"])
            else:
                self.assertEqual(row["reasoning_effort"], "medium")

        estimate = estimate_panel_budget(
            panel,
            load_prices(REPO_ROOT / "prices" / "openrouter-2026-07-03.json"),
            task_count=1,
            rollouts_per_task=1,
            token_basis=TokenBasis(),
        )

        self.assertEqual(estimate["rows"], 5)
        self.assertEqual(estimate["priced_rows"], 5)
        self.assertEqual(estimate["missing_price_rows"], 0)

    def test_lowest_preview_panel_is_priced_and_uses_low_where_available(self) -> None:
        panel = load_panel(REPO_ROOT / "panels" / "deepswe-v1.1-lowest-preview.json")
        rows = panel["rows"]
        effort_by_id = {row["id"]: row["reasoning_effort"] for row in rows}

        self.assertEqual(
            effort_by_id,
            {
                "mini_swe_agent_gpt_5_5_low": "low",
                "mini_swe_agent_claude_opus_4_8_low": "low",
                "mini_swe_agent_claude_sonnet_5_low": "low",
                "mini_swe_agent_gemini_3_5_flash_medium": "medium",
                "mini_swe_agent_kimi_k2_7_code_default": None,
            },
        )
        self.assertFalse(any("fable" in row["id"] for row in rows))
        self.assertFalse(any("laguna" in row["id"] for row in rows))

        estimate = estimate_panel_budget(
            panel,
            load_prices(REPO_ROOT / "prices" / "openrouter-2026-07-03.json"),
            task_count=1,
            rollouts_per_task=1,
            token_basis=TokenBasis(),
        )

        self.assertEqual(estimate["rows"], 5)
        self.assertEqual(estimate["priced_rows"], 5)
        self.assertEqual(estimate["missing_price_rows"], 0)

    def test_codex_mini_calibration_panel_is_priced(self) -> None:
        estimate = estimate_panel_budget(
            load_panel(REPO_ROOT / "panels" / "shallowswe-codex-mini-calibration-v0.1.json"),
            load_prices(REPO_ROOT / "prices" / "openai-2026-07-06.json"),
            task_count=18,
            rollouts_per_task=3,
            token_basis=TokenBasis(input_tokens=10_000, output_tokens=1_000),
            max_budget_usd=5,
        )

        self.assertEqual(estimate["rows"], 2)
        self.assertEqual(estimate["priced_rows"], 2)
        self.assertEqual(estimate["missing_price_rows"], 0)
        self.assertAlmostEqual(estimate["estimated_full_panel_cost_usd"], 1.296)
        self.assertFalse(estimate["over_budget"])

    def test_expanded_pilot_panel_is_priced_and_keeps_effort_variants_separate(self) -> None:
        panel = load_panel(REPO_ROOT / "panels" / "deepswe-v1.1-expanded-pilot.json")
        rows = panel["rows"]
        effort_by_id = {row["id"]: row["reasoning_effort"] for row in rows}

        self.assertEqual(
            effort_by_id,
            {
                "mini_swe_agent_claude_fable_5_low": "low",
                "mini_swe_agent_claude_sonnet_5_low": "low",
                "mini_swe_agent_claude_sonnet_5_medium": "medium",
                "mini_swe_agent_claude_opus_4_8_low": "low",
                "mini_swe_agent_claude_opus_4_8_medium": "medium",
                "mini_swe_agent_gpt_5_5_low": "low",
                "mini_swe_agent_gpt_5_5_medium": "medium",
                "mini_swe_agent_gemini_3_5_flash_medium": "medium",
                "mini_swe_agent_glm_5_2_high": "high",
                "mini_swe_agent_kimi_k2_7_code_default": None,
            },
        )
        self.assertTrue(any("fable" in row["id"] for row in rows))
        self.assertFalse(any("laguna" in row["id"] for row in rows))

        estimate = estimate_panel_budget(
            panel,
            load_prices(REPO_ROOT / "prices" / "openrouter-2026-07-03.json"),
            task_count=1,
            rollouts_per_task=1,
            token_basis=TokenBasis(),
        )

        self.assertEqual(estimate["rows"], 10)
        self.assertEqual(estimate["priced_rows"], 10)
        self.assertEqual(estimate["missing_price_rows"], 0)

    def test_budget_limit_marks_over_budget_estimates(self) -> None:
        panel = {
            "rows": [
                {
                    "id": "expensive",
                    "model": "expensive",
                }
            ]
        }
        prices = {
            "expensive": ModelPrice(
                input_per_1m=100.0,
                cached_input_per_1m=None,
                output_per_1m=100.0,
            )
        }

        estimate = estimate_panel_budget(
            panel,
            prices,
            task_count=10,
            rollouts_per_task=10,
            token_basis=TokenBasis(input_tokens=10_000, output_tokens=10_000),
            max_budget_usd=100.0,
        )

        self.assertGreater(estimate["estimated_full_panel_cost_usd"], 100.0)
        self.assertTrue(estimate["over_budget"])
        self.assertEqual(estimate["budget_limit_usd"], 100.0)

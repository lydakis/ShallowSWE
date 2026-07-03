from __future__ import annotations

from pathlib import Path
import unittest

from shallowswe.results import load_prices, rollout_cost_usd, row_from_mapping


REPO_ROOT = Path(__file__).resolve().parents[1]


class OpenRouterPriceSheetTests(unittest.TestCase):
    def test_cheap_smoke_models_are_priced(self) -> None:
        prices = load_prices(REPO_ROOT / "prices" / "openrouter-2026-07-03.json")
        for model in (
            "poolside/laguna-xs-2.1",
            "moonshotai/kimi-k2.7-code",
            "z-ai/glm-5.2",
            "google/gemini-3.5-flash",
        ):
            row = row_from_mapping(
                {
                    "model": model,
                    "task_id": "py-normalize-username",
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

            self.assertGreaterEqual(rollout_cost_usd(row, prices), 0.0)

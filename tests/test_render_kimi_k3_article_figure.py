from __future__ import annotations

import unittest

from scripts.render_kimi_k3_article_figure import render_svg


class KimiK3ArticleFigureTests(unittest.TestCase):
    def test_svg_contains_both_panels_and_fresh_context_caveat(self) -> None:
        analysis = {
            "standalone": {
                "models": {
                    symbol: {
                        "label": label,
                        "pass_rate": 0.6 + index * 0.01,
                        "pass_rate_ci": [0.55, 0.7],
                        "realized_cpsc_usd": 4.0 + index,
                    }
                    for index, (symbol, label) in enumerate(
                        {
                            "G": "Grok",
                            "S": "Sol high",
                            "X": "Sol xhigh",
                            "M": "Sol max",
                            "T": "Terra max",
                            "L": "Luna max",
                            "K": "Kimi K3 max",
                            "F": "Fable xhigh",
                        }.items()
                    )
                },
                "k3_cache_sensitivity": [
                    {"cache_fraction": 0.9342, "realized_cpsc_usd": 8.0},
                    {"cache_fraction": 0.98, "realized_cpsc_usd": 6.5},
                    {"cache_fraction": 1.0, "realized_cpsc_usd": 5.8},
                ],
            },
            "retry": {
                "models": {
                    symbol: {
                        "label": label,
                        "curve": [
                            {
                                "attempts": attempts,
                                "coverage": 0.6 + attempts * 0.05,
                                "stopped_cost_per_task_usd": (index + 2) * attempts,
                            }
                            for attempts in range(1, 5)
                        ],
                    }
                    for index, (symbol, label) in enumerate(
                        {
                            "K": "Kimi K3 max",
                            "S": "Sol high",
                            "L": "Luna max",
                            "F": "Fable xhigh",
                        }.items()
                    )
                }
            },
        }
        svg = render_svg(analysis)
        self.assertIn("Panel A", svg)
        self.assertIn("Panel B", svg)
        self.assertIn("fresh-context retries", svg)
        self.assertIn('viewBox="0 0 1280 780"', svg)


if __name__ == "__main__":
    unittest.main()

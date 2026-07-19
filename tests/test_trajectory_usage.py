from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.results import ModelPrice
from shallowswe.trajectory_usage import (
    canonical_usage_cost_from_trajectory,
    raw_usage_totals_from_trajectory,
)


class TrajectoryUsageTests(unittest.TestCase):
    def test_reconstructs_tiered_openrouter_cost_per_call(self) -> None:
        trajectory = {
            "messages": [
                {"extra": {"usage": {"input_tokens": 50, "output_tokens": 10}}},
                {
                    "extra": {
                        "usage": {
                            "input_tokens": 150,
                            "output_tokens": 10,
                            "prompt_tokens_details": {
                                "cached_tokens": 30,
                                "cache_write_tokens": 20,
                            },
                        }
                    }
                },
            ]
        }
        price = ModelPrice(
            input_per_1m=1.0,
            cached_input_per_1m=0.5,
            output_per_1m=10.0,
            cache_write_per_1m=1.25,
            long_context_threshold_tokens=100,
            long_context_input_per_1m=2.0,
            long_context_cached_input_per_1m=1.0,
            long_context_cache_write_per_1m=3.0,
            long_context_output_per_1m=15.0,
        )

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.json"
            path.write_text(json.dumps(trajectory))
            totals = raw_usage_totals_from_trajectory(path)
            cost = canonical_usage_cost_from_trajectory(path, price)

        self.assertIsNotNone(totals)
        assert totals is not None
        self.assertEqual(totals["peak_context_tokens"], 150)
        self.assertEqual(totals["cache_read_tokens"], 30)
        self.assertEqual(totals["cache_write_tokens"], 20)
        self.assertAlmostEqual(cost or 0.0, 0.00059)


if __name__ == "__main__":
    unittest.main()

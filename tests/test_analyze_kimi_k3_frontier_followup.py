from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.analyze_kimi_k3_frontier_followup import (
    aggregate_policy,
    bootstrap_seeds,
    configured_cache_fractions,
    enumerate_policy_sequences,
    k3_repriced_cost,
    linear_break_even_fraction,
    summarize_task_policy,
)


def _trial(
    *,
    name: str,
    passed: bool,
    cost: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict[str, object]:
    return {
        "trial_name": name,
        "passed": passed,
        "cost_usd": cost,
        "n_input_tokens": input_tokens,
        "n_output_tokens": output_tokens,
        "n_agent_steps": 1,
        "agent_duration_seconds": 2.0,
        "trial_duration_seconds": 3.0,
        "error_category": None,
    }


class KimiK3FrontierRetrospectiveTests(unittest.TestCase):
    def test_checked_in_spec_is_existing_data_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        spec = json.loads(
            (
                root
                / "configs/analyses/kimi-k3-frontier-retrospective-2026-07-19/spec.json"
            ).read_text()
        )

        self.assertEqual(spec["status"], "existing_data_only_no_runs_authorized")
        self.assertTrue(spec["claim_boundary"]["no_paid_run_authorization"])
        self.assertTrue(spec["claim_boundary"]["newly_generated_model_outcomes_excluded"])
        self.assertNotIn("targeted_ten_operational_study", spec)
        self.assertNotIn("portfolio_followup", spec)
        self.assertNotIn("hypotheses", spec)

    def test_protocol_controls_are_machine_reproducible(self) -> None:
        protocol = {
            "cache_accounting": {
                "fallback_cache_fractions": [0.0, 0.5, 0.9, 0.95, 0.98, 1.0],
                "supplemental_research_cache_fractions": [0.9341821464, 0.96, 0.97],
            }
        }

        self.assertEqual(
            configured_cache_fractions(protocol),
            (0.0, 0.5, 0.9, 0.9341821464, 0.95, 0.96, 0.97, 0.98, 1.0),
        )
        self.assertEqual(
            bootstrap_seeds(20_260_719),
            {"task_cluster": 20_260_719, "repository_cluster": 20_260_719},
        )
        self.assertEqual(
            linear_break_even_fraction(2.0, -2.0),
            {
                "cache_fraction": 0.5,
                "feasible": True,
                "value_at_zero": 2.0,
                "value_at_one": -2.0,
            },
        )
        self.assertFalse(linear_break_even_fraction(2.0, 1.0)["feasible"])

    def test_exhaustive_assignment_is_invariant_to_attempt_input_order(self) -> None:
        attempts = {
            "A": [
                _trial(name="a-fail-cheap", passed=False, cost=1.0),
                _trial(name="a-pass", passed=True, cost=3.0),
                _trial(name="a-fail-expensive", passed=False, cost=5.0),
            ],
            "B": [_trial(name="b-pass", passed=True, cost=7.0)],
        }

        sequences = list(enumerate_policy_sequences(("A", "A", "B"), attempts))
        forward = summarize_task_policy(("A", "A", "B"), attempts)
        reversed_attempts = {"A": list(reversed(attempts["A"])), "B": attempts["B"]}
        reversed_summary = summarize_task_policy(("A", "A", "B"), reversed_attempts)

        self.assertEqual(len(sequences), 6)
        self.assertEqual(
            {tuple(row["trial_name"] for _, row in sequence) for sequence in sequences},
            {
                ("a-fail-cheap", "a-pass", "b-pass"),
                ("a-fail-cheap", "a-fail-expensive", "b-pass"),
                ("a-pass", "a-fail-cheap", "b-pass"),
                ("a-pass", "a-fail-expensive", "b-pass"),
                ("a-fail-expensive", "a-fail-cheap", "b-pass"),
                ("a-fail-expensive", "a-pass", "b-pass"),
            },
        )
        self.assertEqual(forward, reversed_summary)

    def test_k3_repricing_and_stopped_cost_follow_cache_fraction(self) -> None:
        k3 = _trial(
            name="k3-pass",
            passed=True,
            cost=99.0,
            input_tokens=1_000_000,
            output_tokens=100_000,
        )

        self.assertAlmostEqual(k3_repriced_cost(k3, cache_fraction=0.0), 4.5)
        self.assertAlmostEqual(k3_repriced_cost(k3, cache_fraction=0.5), 3.15)
        self.assertAlmostEqual(k3_repriced_cost(k3, cache_fraction=1.0), 1.8)

        attempts = {
            "G": [_trial(name="g-fail", passed=False, cost=1.0)],
            "S": [
                _trial(name="s-fail-1", passed=False, cost=1.0),
                _trial(name="s-fail-2", passed=False, cost=1.0),
            ],
            "K": [k3],
        }
        no_cache = summarize_task_policy(
            ("G", "S", "S", "K"),
            attempts,
            cache_fraction=0.0,
        )
        all_cache = summarize_task_policy(
            ("G", "S", "S", "K"),
            attempts,
            cache_fraction=1.0,
        )

        self.assertEqual(no_cache["coverage"], 1.0)
        self.assertEqual(all_cache["coverage"], 1.0)
        self.assertAlmostEqual(no_cache["stopped_cost_usd"], 7.5)
        self.assertAlmostEqual(all_cache["stopped_cost_usd"], 4.8)
        self.assertAlmostEqual(
            no_cache["stopped_cost_usd"] - all_cache["stopped_cost_usd"],
            2.7,
        )

        aggregate = aggregate_policy([all_cache])
        self.assertAlmostEqual(aggregate["stopped_agent_steps_per_verified_task"], 4.0)
        self.assertAlmostEqual(aggregate["stopped_agent_hours_per_verified_task"], 8 / 3600)
        self.assertAlmostEqual(aggregate["stopped_trial_hours_per_verified_task"], 12 / 3600)


if __name__ == "__main__":
    unittest.main()

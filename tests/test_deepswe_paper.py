from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from shallowswe.deepswe_paper import write_deepswe_paper_assets


def _configuration(
    config: str,
    model: str,
    *,
    pass_rate: float,
    pass_rank: float,
    cpsc: float,
    cpsc_rank: float,
    successful_spend: float,
    reliability_tax: float,
) -> dict[str, object]:
    return {
        "config": config,
        "model": model,
        "reasoning_effort": "medium",
        "attempts": 2,
        "successes": 1,
        "failures": 1,
        "pass_rate": pass_rate,
        "pass_rate_rank": pass_rank,
        "realized_cpsc_usd": cpsc,
        "realized_cpsc_rank": cpsc_rank,
        "rank_displacement": cpsc_rank - pass_rank,
        "mean_cost_per_attempt_usd": cpsc * pass_rate,
        "conditional_successful_spend_usd": successful_spend,
        "conditional_failed_spend_usd": reliability_tax,
        "realized_reliability_tax_usd": reliability_tax,
        "realized_reliability_tax_share": reliability_tax / cpsc,
        "attempt_cost_pareto_frontier": True,
        "imputed_cost_rows": 0,
    }


class DeepSWEPaperAssetTests(unittest.TestCase):
    def test_writes_auditable_tables_figures_and_manifest(self) -> None:
        rows = [
            _configuration(
                "config-a",
                "gpt-5-6-sol",
                pass_rate=0.75,
                pass_rank=1.0,
                cpsc=10.0,
                cpsc_rank=2.0,
                successful_spend=7.0,
                reliability_tax=3.0,
            ),
            _configuration(
                "config-b",
                "gpt-5-6-luna",
                pass_rate=0.50,
                pass_rank=2.0,
                cpsc=4.0,
                cpsc_rank=1.0,
                successful_spend=2.0,
                reliability_tax=2.0,
            ),
        ]
        report = {
            "schema_version": "shallowswe.deepswe_economics.v0.1",
            "benchmark_release": "DeepSWE v1.1",
            "primary": {
                "cohort": {"source_rows": 4, "scored_rows": 4, "excluded_rows": 0},
                "missing_cost": {"scored_missing_rows": 0},
                "rank_association": {"spearman": -1.0, "kendall_tau_b": -1.0},
                "display_rank_association": {"spearman": -1.0, "kendall_tau_b": -1.0},
                "effort_rank_association": {
                    "pooled_within_model": {
                        "models": 0,
                        "configurations": 0,
                        "spearman": None,
                        "kendall_tau_b": None,
                    },
                    "by_model": [],
                },
                "configurations": rows,
                "resource_intensity": [],
                "display_configurations": rows,
                "task_mix": {
                    "success_heterogeneity": [],
                    "matched_solved_task_comparisons": [],
                    "panel_solvedness_strata": {
                        "tasks": [],
                        "configurations": [],
                        "summaries": [],
                    },
                    "leave_one_family_out_panel_solvedness": {
                        "assignments": [],
                        "configurations": [],
                    },
                    "gpt_5_6_group_out_panel_solvedness": {
                        "assignments": [],
                        "configurations": [],
                    },
                },
                "infrastructure_exclusion_audit": {
                    "status": "test",
                    "source_rows": 4,
                    "included_rows": 4,
                    "excluded_rows": 0,
                    "configurations": [],
                },
                "task_weighting_sensitivity": {
                    "full_basket_configurations": [],
                    "common_basket_configurations": [],
                    "full_basket_reliability_floor_curve": [],
                },
                "reliability_floor_curve": [
                    {
                        "minimum_pass_rate": 0.0,
                        "eligible_configurations": 2,
                        "minimum_cpsc_config": "config-b",
                        "minimum_cpsc_usd": 4.0,
                        "observed_pass_rate": 0.5,
                    },
                    {
                        "minimum_pass_rate": 0.75,
                        "eligible_configurations": 1,
                        "minimum_cpsc_config": "config-a",
                        "minimum_cpsc_usd": 10.0,
                        "observed_pass_rate": 0.75,
                    },
                ],
            },
            "bootstrap": {
                "replicates": 100,
                "cluster_count": 2,
                "configurations": [],
                "paired_comparisons": [],
                "resource_intensity": [],
                "paired_resource_comparisons": [],
                "rank_association_intervals": {
                    "all_configurations": {
                        "spearman_ci_low": -1.0,
                        "spearman_ci_high": -1.0,
                    },
                    "fixed_display_panel": {
                        "spearman_ci_low": -1.0,
                        "spearman_ci_high": -1.0,
                    },
                    "pooled_within_model": {
                        "spearman_ci_low": -1.0,
                        "spearman_ci_high": -1.0,
                    },
                },
                "within_model_rank_association_intervals": [],
                "reliability_floor_policy": [],
                "reliability_floor_lcb_eligibility": [],
                "reliability_floor_selection_frequencies": [],
                "task_weighting_sensitivity": {
                    "reliability_floor_policy": [],
                    "reliability_floor_selection_frequencies": [],
                },
            },
            "missing_cost_sensitivities": [],
            "failure_charge_sensitivity": {"scenarios": []},
            "leaderboard_reconciliation": {"all_match": True},
            "provider_cost_provenance": [],
            "source_metadata": {},
            "anchor_success_budget_sensitivity": {"scenarios": []},
            "repository_cluster_sensitivity": {
                "paired_comparisons": [],
                "paired_resource_comparisons": [],
                "reliability_floor_policy": [],
                "reliability_floor_selection_frequencies": [],
            },
            "paired_outcome_dispersion": {
                "status": "result_informed_exploratory_outcome_dispersion",
                "rows": [
                    {
                        "row_type": "contrast_a_minus_b",
                        "config_a": "config-b",
                        "config_b": "config-a",
                        "middle_outcome_share_difference": 0.25,
                    }
                ],
            },
        }
        trials = {
            "rows": [
                {
                    "trial_name": "trial-a",
                    "task_name": "task-a",
                    "source": "deep-swe",
                    "eval_scope": "full",
                    "model": "gpt-5-6-sol",
                    "provider": "openai",
                    "harness": "mini-swe-agent",
                    "config": "config-a",
                    "reasoning_effort": "medium",
                    "passed": True,
                    "outcome": "pass",
                    "included_in_score": True,
                    "cost_usd": 2.0,
                    "n_input_tokens": 100,
                    "n_cache_tokens": 0,
                    "n_output_tokens": 10,
                    "n_agent_steps": 2,
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / ".DS_Store").write_bytes(b"finder metadata")
            manifest = write_deepswe_paper_assets(trials, report, output)

            self.assertTrue((output / "tables" / "derived-trials.csv").exists())
            self.assertTrue((output / "tables" / "configuration-results.csv").exists())
            self.assertTrue(
                (output / "tables" / "infrastructure-exclusion-audit.csv").exists()
            )
            self.assertTrue(
                (output / "tables" / "reliability-floor-bootstrap.csv").exists()
            )
            self.assertTrue(
                (output / "tables" / "provider-cost-provenance.csv").exists()
            )
            self.assertTrue(
                (output / "tables" / "panel-solvedness-strata.csv").exists()
            )
            self.assertTrue(
                (
                    output
                    / "tables"
                    / "leave-one-family-out-panel-solvedness.csv"
                ).exists()
            )
            self.assertTrue(
                (output / "tables" / "anchor-success-budget-sensitivity.csv").exists()
            )
            self.assertTrue(
                (output / "tables" / "equal-task-full-basket.csv").exists()
            )
            self.assertTrue(
                (output / "tables" / "equal-task-bootstrap.csv").exists()
            )
            self.assertTrue((output / "tables" / "economic-frontier.csv").exists())
            self.assertTrue((output / "tables" / "resource-intensity.csv").exists())
            self.assertTrue(
                (output / "tables" / "paired-resource-comparisons.csv").exists()
            )
            self.assertTrue(
                (
                    output
                    / "tables"
                    / "repository-bootstrap-paired-comparisons.csv"
                ).exists()
            )
            self.assertTrue(
                (output / "tables" / "paired-outcome-dispersion.csv").exists()
            )
            self.assertTrue((output / "figures" / "rank-divergence.svg").exists())
            self.assertTrue((output / "figures" / "economic-frontier.svg").exists())
            self.assertTrue((output / "figures" / "reliability-floor.svg").exists())
            self.assertTrue((output / "figures" / "failure-cost-decomposition.svg").exists())
            self.assertTrue((output / "figures" / "task-coverage.svg").exists())
            self.assertTrue(
                (output / "figures" / "invoice-work-frontiers.svg").exists()
            )
            self.assertTrue((output / "summary.json").exists())
            self.assertEqual(json.loads((output / "manifest.json").read_text()), manifest)
            self.assertNotIn(".DS_Store", {row["path"] for row in manifest["files"]})
            self.assertGreater(len(manifest["files"]), 8)
            self.assertIn("Pass-rate rank", (output / "figures" / "rank-divergence.svg").read_text())
            self.assertIn(
                "Solve rate versus mean attempt cost",
                (output / "figures" / "economic-frontier.svg").read_text(),
            )
            reliability_svg = (output / "figures" / "reliability-floor.svg").read_text()
            self.assertIn("Panel A", reliability_svg)
            self.assertIn("Panel B", reliability_svg)
            self.assertIn("No eligible", reliability_svg)
            self.assertNotIn("Lower-bound eligibility", reliability_svg)


if __name__ == "__main__":
    unittest.main()

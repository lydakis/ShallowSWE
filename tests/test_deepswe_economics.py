from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from shallowswe.deepswe_economics import (
    analyze_anchor_success_budget_sensitivity,
    analyze_deepswe_trials,
    analyze_failure_charge_sensitivity,
    bootstrap_deepswe_trials,
    derive_deepswe_trial_rows,
    verify_artifact,
)


def _row(
    trial_name: str,
    *,
    config: str = "config-a",
    model: str = "model-a",
    passed: bool,
    cost_usd: float | None,
    included_in_score: bool = True,
    outcome: str | None = None,
    task_name: str | None = None,
    error_category: str | None = None,
) -> dict[str, object]:
    return {
        "trial_name": trial_name,
        "task_name": task_name or ("task-a" if trial_name.endswith("1") else "task-b"),
        "source": "deep-swe",
        "eval_scope": "full",
        "model": model,
        "provider": "provider",
        "harness": "mini-swe-agent",
        "config": config,
        "reasoning_effort": "medium",
        "passed": passed,
        "errored": not included_in_score,
        "outcome": outcome or ("pass" if passed else "fail"),
        "included_in_score": included_in_score,
        "error_category": error_category,
        "cost_usd": cost_usd,
        "n_input_tokens": 100,
        "n_cache_tokens": 20,
        "n_output_tokens": 10,
        "n_agent_steps": 4,
        "agent_duration_seconds": 60.0,
        "trial_duration_seconds": 75.0,
    }


class DeepSWEEconomicsTests(unittest.TestCase):
    def test_realized_cpsc_uses_scored_rows_and_decomposes_exactly(self) -> None:
        payload = {
            "rows": [
                _row("trial-1", passed=True, cost_usd=2.0),
                _row("trial-2", passed=True, cost_usd=4.0),
                _row("trial-3", passed=False, cost_usd=6.0),
                _row(
                    "trial-4",
                    passed=False,
                    cost_usd=100.0,
                    included_in_score=False,
                    outcome="excluded_error",
                ),
            ]
        }

        analysis = analyze_deepswe_trials(payload)
        row = analysis["configurations"][0]

        self.assertEqual(analysis["cohort"]["source_rows"], 4)
        self.assertEqual(analysis["cohort"]["scored_rows"], 3)
        self.assertEqual(analysis["cohort"]["excluded_rows"], 1)
        self.assertEqual(row["attempts"], 3)
        self.assertEqual(row["successes"], 2)
        self.assertEqual(row["failures"], 1)
        self.assertAlmostEqual(row["pass_rate"], 2 / 3)
        self.assertAlmostEqual(row["conditional_successful_spend_usd"], 3.0)
        self.assertAlmostEqual(row["conditional_failed_spend_usd"], 6.0)
        self.assertAlmostEqual(row["realized_reliability_tax_usd"], 3.0)
        self.assertAlmostEqual(row["realized_cpsc_usd"], 6.0)
        self.assertAlmostEqual(
            row["realized_cpsc_usd"],
            row["conditional_successful_spend_usd"]
            + row["realized_reliability_tax_usd"],
        )
        self.assertAlmostEqual(row["realized_reliability_tax_share"], 0.5)

    def test_primary_missing_cost_rule_imputes_configuration_mean(self) -> None:
        payload = {
            "rows": [
                _row("trial-1", passed=True, cost_usd=2.0),
                _row("trial-2", passed=False, cost_usd=4.0),
                _row("trial-3", passed=False, cost_usd=None),
            ]
        }

        analysis = analyze_deepswe_trials(payload)
        row = analysis["configurations"][0]

        self.assertEqual(analysis["missing_cost"]["scored_missing_rows"], 1)
        self.assertEqual(row["imputed_cost_rows"], 1)
        self.assertAlmostEqual(row["total_cost_usd"], 9.0)
        self.assertAlmostEqual(row["conditional_failed_spend_usd"], 3.5)
        self.assertAlmostEqual(row["realized_cpsc_usd"], 9.0)

    def test_derived_trial_rows_preserve_reported_and_analysis_cost(self) -> None:
        payload = {
            "rows": [
                _row("trial-1", passed=True, cost_usd=2.0),
                _row("trial-2", passed=False, cost_usd=None),
            ]
        }

        rows = derive_deepswe_trial_rows(payload)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["reported_cost_usd"], 2.0)
        self.assertEqual(rows[0]["analysis_cost_usd"], 2.0)
        self.assertEqual(rows[0]["agent_duration_seconds"], 60.0)
        self.assertEqual(rows[0]["trial_duration_seconds"], 75.0)
        self.assertFalse(rows[0]["cost_imputed"])
        self.assertIsNone(rows[1]["reported_cost_usd"])
        self.assertEqual(rows[1]["analysis_cost_usd"], 2.0)
        self.assertTrue(rows[1]["cost_imputed"])

    def test_complete_case_sensitivity_removes_row_from_both_denominators(self) -> None:
        payload = {
            "rows": [
                _row("trial-1", passed=True, cost_usd=2.0),
                _row("trial-2", passed=False, cost_usd=None),
            ]
        }

        analysis = analyze_deepswe_trials(payload, missing_cost_method="complete_case")
        row = analysis["configurations"][0]

        self.assertEqual(analysis["cohort"]["analysis_rows"], 1)
        self.assertEqual(row["attempts"], 1)
        self.assertEqual(row["successes"], 1)
        self.assertEqual(row["failures"], 0)
        self.assertAlmostEqual(row["pass_rate"], 1.0)
        self.assertAlmostEqual(row["realized_cpsc_usd"], 2.0)

    def test_zero_success_configuration_remains_visible_with_undefined_cpsc(self) -> None:
        payload = {
            "rows": [
                _row("trial-1", passed=False, cost_usd=1.0),
                _row("trial-2", passed=False, cost_usd=2.0),
            ]
        }

        row = analyze_deepswe_trials(payload)["configurations"][0]

        self.assertEqual(row["successes"], 0)
        self.assertIsNone(row["realized_cpsc_usd"])
        self.assertIsNone(row["conditional_successful_spend_usd"])
        self.assertIsNone(row["realized_reliability_tax_usd"])

    def test_ranks_pass_rate_and_cpsc_independently(self) -> None:
        payload = {
            "rows": [
                _row("a-1", config="config-a", model="model-a", passed=True, cost_usd=10.0),
                _row("a-2", config="config-a", model="model-a", passed=True, cost_usd=10.0),
                _row("b-1", config="config-b", model="model-b", passed=True, cost_usd=1.0),
                _row("b-2", config="config-b", model="model-b", passed=False, cost_usd=1.0),
            ]
        }

        analysis = analyze_deepswe_trials(payload)
        rows = {row["config"]: row for row in analysis["configurations"]}

        self.assertEqual(rows["config-a"]["pass_rate_rank"], 1)
        self.assertEqual(rows["config-b"]["pass_rate_rank"], 2)
        self.assertEqual(rows["config-b"]["realized_cpsc_rank"], 1)
        self.assertEqual(rows["config-a"]["realized_cpsc_rank"], 2)
        self.assertEqual(rows["config-a"]["rank_displacement"], 1)
        self.assertEqual(rows["config-b"]["rank_displacement"], -1)
        self.assertAlmostEqual(analysis["rank_association"]["spearman"], -1.0)
        self.assertAlmostEqual(analysis["rank_association"]["kendall_tau_b"], -1.0)

    def test_reports_invoice_and_resource_intensity_as_separate_surfaces(self) -> None:
        payload = {
            "rows": [
                _row(
                    "a-1",
                    config="config-a",
                    model="model-a",
                    passed=True,
                    cost_usd=10.0,
                ),
                _row(
                    "a-2",
                    config="config-a",
                    model="model-a",
                    passed=False,
                    cost_usd=10.0,
                ),
                _row(
                    "b-1",
                    config="config-b",
                    model="model-b",
                    passed=True,
                    cost_usd=1.0,
                ),
            ]
        }

        analysis = analyze_deepswe_trials(payload)
        rows = {row["config"]: row for row in analysis["resource_intensity"]}

        self.assertAlmostEqual(rows["config-a"]["agent_steps_per_success"], 8.0)
        self.assertAlmostEqual(rows["config-a"]["input_tokens_per_success"], 200.0)
        self.assertAlmostEqual(rows["config-a"]["cache_tokens_per_success"], 40.0)
        self.assertAlmostEqual(rows["config-a"]["output_tokens_per_success"], 20.0)
        self.assertAlmostEqual(rows["config-a"]["agent_seconds_per_success"], 120.0)
        self.assertAlmostEqual(rows["config-a"]["trial_seconds_per_success"], 150.0)
        self.assertEqual(rows["config-b"]["agent_steps_per_success_rank"], 1.0)
        self.assertEqual(rows["config-b"]["reported_cpsc_rank"], 1.0)
        self.assertTrue(rows["config-b"]["agent_steps_per_success_pareto_frontier"])
        self.assertFalse(rows["config-a"]["agent_steps_per_success_pareto_frontier"])

    def test_resource_metric_is_undefined_when_any_scored_row_is_missing(self) -> None:
        complete = _row(
            "complete-1",
            config="config-complete",
            model="model-complete",
            passed=True,
            cost_usd=1.0,
        )
        incomplete = _row(
            "incomplete-1",
            config="config-incomplete",
            model="model-incomplete",
            passed=True,
            cost_usd=1.0,
        )
        incomplete["n_agent_steps"] = None

        analysis = analyze_deepswe_trials({"rows": [complete, incomplete]})
        rows = {row["config"]: row for row in analysis["resource_intensity"]}

        self.assertEqual(rows["config-incomplete"]["n_agent_steps_missing_rows"], 1)
        self.assertIsNone(rows["config-incomplete"]["agent_steps_per_success"])
        self.assertIsNone(rows["config-incomplete"]["agent_steps_per_success_rank"])
        self.assertFalse(
            rows["config-incomplete"]["agent_steps_per_success_pareto_frontier"]
        )
        self.assertEqual(rows["config-complete"]["agent_steps_per_success_rank"], 1.0)
        self.assertAlmostEqual(
            rows["config-incomplete"]["agent_seconds_per_success"], 60.0
        )

    def test_marks_attempt_cost_frontier_and_builds_reliability_floor_curve(self) -> None:
        payload = {
            "rows": [
                _row("a-1", config="config-a", model="model-a", passed=True, cost_usd=10.0),
                _row("a-2", config="config-a", model="model-a", passed=True, cost_usd=10.0),
                _row("b-1", config="config-b", model="model-b", passed=True, cost_usd=1.0),
                _row("b-2", config="config-b", model="model-b", passed=False, cost_usd=1.0),
                _row("c-1", config="config-c", model="model-c", passed=False, cost_usd=5.0),
                _row("c-2", config="config-c", model="model-c", passed=False, cost_usd=5.0),
            ]
        }

        analysis = analyze_deepswe_trials(payload)
        rows = {row["config"]: row for row in analysis["configurations"]}
        curve = {row["minimum_pass_rate"]: row for row in analysis["reliability_floor_curve"]}

        self.assertTrue(rows["config-a"]["attempt_cost_pareto_frontier"])
        self.assertTrue(rows["config-b"]["attempt_cost_pareto_frontier"])
        self.assertFalse(rows["config-c"]["attempt_cost_pareto_frontier"])
        self.assertEqual(curve[0.0]["minimum_cpsc_config"], "config-b")
        self.assertEqual(curve[0.75]["minimum_cpsc_config"], "config-a")
        self.assertEqual(curve[0.75]["eligible_configurations"], 1)

    def test_reports_equal_task_weighting_separately_from_observed_attempt_pooling(self) -> None:
        rows = [
            _row(
                f"a-task-a-{index}",
                config="config-a",
                model="model-a",
                task_name="task-a",
                passed=True,
                cost_usd=1.0,
            )
            for index in range(4)
        ]
        rows.extend(
            [
                _row(
                    "a-task-b-0",
                    config="config-a",
                    model="model-a",
                    task_name="task-b",
                    passed=False,
                    cost_usd=9.0,
                ),
                _row(
                    "b-task-a-0",
                    config="config-b",
                    model="model-b",
                    task_name="task-a",
                    passed=True,
                    cost_usd=2.0,
                ),
            ]
        )

        analysis = analyze_deepswe_trials({"rows": rows})
        pooled = {row["config"]: row for row in analysis["configurations"]}
        weighting = analysis["task_weighting_sensitivity"]
        equal_task = {
            row["config"]: row for row in weighting["full_basket_configurations"]
        }

        self.assertAlmostEqual(pooled["config-a"]["pass_rate"], 0.8)
        self.assertAlmostEqual(pooled["config-a"]["realized_cpsc_usd"], 3.25)
        self.assertAlmostEqual(equal_task["config-a"]["equal_task_pass_rate"], 0.5)
        self.assertAlmostEqual(equal_task["config-a"]["equal_task_cpsc_usd"], 10.0)
        self.assertTrue(equal_task["config-a"]["full_basket_identified"])
        self.assertFalse(equal_task["config-b"]["full_basket_identified"])
        self.assertEqual(equal_task["config-b"]["missing_task_count"], 1)
        self.assertIsNone(equal_task["config-b"]["equal_task_cpsc_rank"])
        self.assertEqual(weighting["declared_task_count"], 2)
        self.assertEqual(weighting["full_basket_identified_configurations"], 1)
        self.assertEqual(weighting["common_basket_task_count"], 1)
        self.assertEqual(weighting["common_basket_excluded_tasks"], ["task-b"])

    def test_selects_one_highest_pass_configuration_per_model_for_display(self) -> None:
        payload = {
            "rows": [
                _row("a-1", config="model-a-high", model="model-a", passed=True, cost_usd=5.0),
                _row("a-2", config="model-a-high", model="model-a", passed=True, cost_usd=5.0),
                _row("b-1", config="model-a-low", model="model-a", passed=True, cost_usd=1.0),
                _row("b-2", config="model-a-low", model="model-a", passed=False, cost_usd=1.0),
            ]
        }

        analysis = analyze_deepswe_trials(payload)

        self.assertEqual(
            [row["config"] for row in analysis["display_configurations"]],
            ["model-a-high"],
        )

    def test_reports_task_success_heterogeneity_and_matched_solved_tasks(self) -> None:
        rows = []
        outcomes = {
            "config-a": {
                "task-a": (True, True, True, True),
                "task-b": (True, False, False, False),
                "task-c": (False, False, False, False),
            },
            "config-b": {
                "task-a": (True, False, False, False),
                "task-b": (False, False, False, False),
                "task-c": (True, True, True, True),
            },
        }
        for config, task_outcomes in outcomes.items():
            for task_name, attempts in task_outcomes.items():
                for index, passed in enumerate(attempts):
                    rows.append(
                        _row(
                            f"{config}-{task_name}-{index}",
                            config=config,
                            model=f"model-{config[-1]}",
                            task_name=task_name,
                            passed=passed,
                            cost_usd=1.0,
                        )
                    )

        task_mix = analyze_deepswe_trials({"rows": rows})["task_mix"]
        heterogeneity = {
            row["config"]: row for row in task_mix["success_heterogeneity"]
        }
        comparison = task_mix["matched_solved_task_comparisons"][0]

        self.assertEqual(heterogeneity["config-a"]["zero_of_four_tasks"], 1)
        self.assertEqual(heterogeneity["config-a"]["one_to_three_of_four_tasks"], 1)
        self.assertEqual(heterogeneity["config-a"]["four_of_four_tasks"], 1)
        self.assertAlmostEqual(heterogeneity["config-a"]["task_coverage_rate"], 2 / 3)
        self.assertEqual(comparison["matched_tasks"], 1)
        self.assertEqual(comparison["solved_task_union"], 3)
        self.assertAlmostEqual(comparison["solved_task_jaccard"], 1 / 3)
        self.assertAlmostEqual(comparison["config_a_matched_pass_rate"], 1.0)
        self.assertAlmostEqual(comparison["config_b_matched_pass_rate"], 0.25)
        self.assertAlmostEqual(comparison["config_a_matched_cpsc_usd"], 1.0)
        self.assertAlmostEqual(comparison["config_b_matched_cpsc_usd"], 4.0)
        self.assertEqual(
            task_mix["sequential_retry_policy"]["status"],
            "not_identified_from_public_trial_rows",
        )

    def test_audits_exclusions_and_charges_them_as_failed_attempts(self) -> None:
        payload = {
            "rows": [
                _row("trial-1", passed=True, cost_usd=2.0),
                _row("trial-2", passed=False, cost_usd=4.0),
                _row(
                    "trial-3",
                    passed=False,
                    cost_usd=6.0,
                    included_in_score=False,
                    outcome="excluded_error",
                    error_category="provider_timeout",
                ),
                _row(
                    "trial-4",
                    passed=False,
                    cost_usd=None,
                    included_in_score=False,
                    outcome="excluded_error",
                    error_category="rate_limit",
                ),
            ]
        }

        audit = analyze_deepswe_trials(payload)["infrastructure_exclusion_audit"]
        row = audit["configurations"][0]

        self.assertEqual(audit["excluded_rows"], 2)
        self.assertEqual(row["source_attempts"], 4)
        self.assertEqual(row["included_attempts"], 2)
        self.assertEqual(row["excluded_attempts"], 2)
        self.assertEqual(row["excluded_missing_cost_rows"], 1)
        self.assertEqual(
            row["excluded_error_categories"],
            {"provider_timeout": 1, "rate_limit": 1},
        )
        self.assertAlmostEqual(row["included_pass_rate"], 0.5)
        self.assertAlmostEqual(row["exclusions_as_failures_pass_rate"], 0.25)
        self.assertAlmostEqual(
            row["exclusions_as_failures_observed_cost_cpsc_lower_bound_usd"],
            12.0,
        )
        self.assertAlmostEqual(
            row["exclusions_as_failures_config_mean_cost_cpsc_usd"],
            15.0,
        )
        self.assertIn("maximum_cpsc_rank_change", audit)
        self.assertIn("config_mean_reliability_floor_curve", audit)

    def test_builds_panel_solvedness_strata_from_configuration_outcomes(self) -> None:
        rows = []
        for config_index in range(4):
            config = f"config-{config_index}"
            for task_name, solvers in (
                ("rare-task", 1),
                ("contested-task", 3),
                ("common-task", 4),
            ):
                rows.append(
                    _row(
                        f"{config}-{task_name}",
                        config=config,
                        model=f"model-{config_index}",
                        task_name=task_name,
                        passed=config_index < solvers,
                        cost_usd=1.0,
                    )
                )

        strata = analyze_deepswe_trials({"rows": rows})["task_mix"][
            "panel_solvedness_strata"
        ]
        tasks = {row["task_name"]: row for row in strata["tasks"]}
        summaries = {row["stratum"]: row for row in strata["summaries"]}

        self.assertEqual(tasks["rare-task"]["stratum"], "rare")
        self.assertEqual(tasks["contested-task"]["stratum"], "contested")
        self.assertEqual(tasks["common-task"]["stratum"], "common")
        self.assertEqual(tasks["rare-task"]["panel_solving_configurations"], 1)
        self.assertEqual(summaries["rare"]["tasks"], 1)
        self.assertEqual(summaries["contested"]["tasks"], 1)
        self.assertEqual(summaries["common"]["tasks"], 1)
        rare_rows = [
            row for row in strata["configurations"] if row["stratum"] == "rare"
        ]
        self.assertEqual(len(rare_rows), 4)
        self.assertEqual(sum(row["successes"] for row in rare_rows), 1)

    def test_leave_one_family_out_strata_do_not_use_target_family_outcomes(self) -> None:
        rows = []
        for config_index in range(2):
            rows.append(
                _row(
                    f"target-{config_index}",
                    config=f"target-{config_index}",
                    model="target-model",
                    task_name="task-a",
                    passed=True,
                    cost_usd=1.0,
                )
            )
        for config_index in range(4):
            rows.append(
                _row(
                    f"panel-{config_index}",
                    config=f"panel-{config_index}",
                    model=f"panel-model-{config_index}",
                    task_name="task-a",
                    passed=False,
                    cost_usd=1.0,
                )
            )

        diagnostic = analyze_deepswe_trials({"rows": rows})["task_mix"][
            "leave_one_family_out_panel_solvedness"
        ]
        assignment = next(
            row
            for row in diagnostic["assignments"]
            if row["target_model_family"] == "target-model"
        )

        self.assertEqual(assignment["comparison_panel_configurations"], 4)
        self.assertEqual(assignment["panel_solving_configurations"], 0)
        self.assertEqual(assignment["stratum"], "rare")

    def test_task_cluster_bootstrap_is_deterministic_and_pairs_configurations(self) -> None:
        payload = {
            "rows": [
                _row("a-1", config="config-a", model="model-a", passed=True, cost_usd=10.0),
                _row("a-2", config="config-a", model="model-a", passed=True, cost_usd=10.0),
                _row("b-1", config="config-b", model="model-b", passed=True, cost_usd=1.0),
                _row("b-2", config="config-b", model="model-b", passed=False, cost_usd=1.0),
            ]
        }

        first = bootstrap_deepswe_trials(payload, replicates=100, seed=7)
        second = bootstrap_deepswe_trials(payload, replicates=100, seed=7)

        self.assertEqual(first, second)
        self.assertEqual(first["cluster_count"], 2)
        self.assertEqual(first["replicates"], 100)
        rows = {row["config"]: row for row in first["configurations"]}
        self.assertEqual(rows["config-a"]["defined_cpsc_replicates"], 100)
        self.assertLess(
            rows["config-a"]["realized_cpsc_usd_ci_low"],
            rows["config-a"]["realized_cpsc_usd_ci_high"] + 0.001,
        )
        comparison = first["paired_comparisons"][0]
        self.assertEqual(comparison["config_a"], "config-a")
        self.assertEqual(comparison["config_b"], "config-b")
        self.assertEqual(comparison["probability_a_cheaper"], 0.0)
        self.assertLess(comparison["defined_replicates"], 100)
        self.assertIn("pass_rate_difference_ci_low", comparison)
        self.assertIn("pass_rate_difference_ci_high", comparison)
        self.assertIn("bca_log_cpsc_ratio_ci_low", comparison)
        self.assertIn("bca_log_cpsc_ratio_ci_high", comparison)
        self.assertIn("rank_association_intervals", first)
        self.assertIn("resource_intensity", first)
        self.assertIn("paired_resource_comparisons", first)
        self.assertIn("reliability_floor_policy", first)
        self.assertIn("task_weighting_sensitivity", first)
        self.assertIn("reliability_floor_lcb_eligibility", first)
        self.assertIn("reliability_floor_selection_frequencies", first)
        resource_rows = {row["config"]: row for row in first["resource_intensity"]}
        self.assertIn("agent_seconds_per_success_ci_low", resource_rows["config-a"])
        duration_comparisons = [
            row
            for row in first["paired_resource_comparisons"]
            if row["resource_metric"] == "trial_seconds_per_success"
        ]
        self.assertEqual(len(duration_comparisons), 1)
        self.assertIn("realized_cpsc_rank_ci_low", rows["config-a"])
        floor = {
            row["minimum_pass_rate"]: row for row in first["reliability_floor_policy"]
        }[0.5]
        self.assertEqual(
            floor["selection_defined_replicates"]
            + floor["no_eligible_configuration_replicates"],
            100,
        )
        frequencies = [
            row
            for row in first["reliability_floor_selection_frequencies"]
            if row["minimum_pass_rate"] == 0.5
        ]
        self.assertEqual(
            sum(row["selection_count"] for row in frequencies),
            floor["selection_defined_replicates"],
        )
        equal_task = first["task_weighting_sensitivity"]
        self.assertEqual(equal_task["task_weighting"], "equal_task")
        self.assertEqual(equal_task["complete_basket_configurations"], 2)
        self.assertEqual(equal_task["incomplete_basket_configurations"], [])
        equal_floor = {
            row["minimum_pass_rate"]: row
            for row in equal_task["reliability_floor_policy"]
        }[0.5]
        self.assertEqual(
            equal_floor["selection_defined_replicates"]
            + equal_floor["no_eligible_configuration_replicates"],
            100,
        )

    def test_failure_charge_sensitivity_uses_anchor_task_costs(self) -> None:
        anchor_a = _row(
            "anchor-1",
            config="anchor",
            model="anchor-model",
            passed=True,
            cost_usd=10.0,
        )
        anchor_b = _row(
            "anchor-2",
            config="anchor",
            model="anchor-model",
            passed=True,
            cost_usd=20.0,
        )
        candidate_a = _row(
            "candidate-1",
            config="candidate",
            model="candidate-model",
            passed=True,
            cost_usd=1.0,
        )
        candidate_b = _row(
            "candidate-2",
            config="candidate",
            model="candidate-model",
            passed=False,
            cost_usd=2.0,
        )
        anchor_a["task_name"] = candidate_a["task_name"] = "task-a"
        anchor_b["task_name"] = candidate_b["task_name"] = "task-b"
        payload = {"rows": [anchor_a, anchor_b, candidate_a, candidate_b]}

        result = analyze_failure_charge_sensitivity(
            payload,
            anchor_config="anchor",
            multipliers=(0.5, 1.0),
        )
        by_multiplier = {row["multiplier"]: row for row in result["scenarios"]}
        half_rows = {
            row["config"]: row for row in by_multiplier[0.5]["configurations"]
        }
        full_rows = {
            row["config"]: row for row in by_multiplier[1.0]["configurations"]
        }

        self.assertEqual(result["status"], "retrospective_sensitivity_not_calibration")
        self.assertEqual(result["anchor_task_coverage"], 2)
        self.assertAlmostEqual(
            half_rows["candidate"]["proxy_failure_charge_cpsc_usd"], 11.0
        )
        self.assertAlmostEqual(
            full_rows["candidate"]["proxy_failure_charge_cpsc_usd"], 21.0
        )
        self.assertAlmostEqual(
            full_rows["candidate"]["proxy_failure_charge_reliability_tax_usd"],
            20.0,
        )
        self.assertNotIn("reference_budget_cpsc_usd", full_rows["candidate"])

    def test_anchor_success_budget_uses_only_tasks_the_anchor_solves(self) -> None:
        rows = [
            _row(
                "anchor-a-1",
                config="anchor",
                model="anchor-model",
                task_name="task-a",
                passed=True,
                cost_usd=10.0,
            ),
            _row(
                "anchor-a-2",
                config="anchor",
                model="anchor-model",
                task_name="task-a",
                passed=True,
                cost_usd=20.0,
            ),
            _row(
                "anchor-b",
                config="anchor",
                model="anchor-model",
                task_name="task-b",
                passed=False,
                cost_usd=5.0,
            ),
            _row(
                "candidate-a-1",
                config="candidate",
                model="candidate-model",
                task_name="task-a",
                passed=True,
                cost_usd=1.0,
            ),
            _row(
                "candidate-a-2",
                config="candidate",
                model="candidate-model",
                task_name="task-a",
                passed=False,
                cost_usd=2.0,
            ),
            _row(
                "candidate-b",
                config="candidate",
                model="candidate-model",
                task_name="task-b",
                passed=True,
                cost_usd=1.0,
            ),
        ]

        result = analyze_anchor_success_budget_sensitivity(
            {"rows": rows},
            anchor_config="anchor",
            multipliers=(1.0,),
        )
        scenario = result["scenarios"][0]
        candidate = {
            row["config"]: row for row in scenario["configurations"]
        }["candidate"]

        self.assertEqual(result["common_basket_tasks"], 1)
        self.assertEqual(result["anchor_unsolved_tasks"], 1)
        self.assertEqual(result["omitted_task_names"], ["task-b"])
        self.assertAlmostEqual(result["base_budget_summary_usd"]["median"], 15.0)
        self.assertEqual(candidate["attempts"], 2)
        self.assertAlmostEqual(candidate["proxy_failure_charge_cpsc_usd"], 16.0)

    def test_verify_artifact_checks_size_and_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            path.write_text(json.dumps({"ok": True}))

            report = verify_artifact(
                path,
                expected_bytes=12,
                expected_sha256="6bc0da1f42f96fc37b8bd7ed20ba57606d2a0da5cda2b135c7854fbdc985b8a3",
            )

        self.assertTrue(report["verified"])
        self.assertEqual(report["bytes"], 12)


if __name__ == "__main__":
    unittest.main()

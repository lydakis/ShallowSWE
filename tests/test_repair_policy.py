from __future__ import annotations

import unittest
from dataclasses import replace

from shallowswe.results import repair_loop_from_mapping
from shallowswe.repair_policy import build_repair_policy


def _checkpoint(submission: int, spend: float, steps: int, *, passed: bool) -> dict[str, object]:
    return {
        "event_index": submission * 2,
        "event_type": "verifier_result",
        "agent_submission": submission,
        "verifier_submission": submission,
        "result_class": "passed" if passed else "output_mismatch",
        "cumulative_input_tokens": 100 * submission,
        "cumulative_output_tokens": 10 * submission,
        "cumulative_cache_read_tokens": 0,
        "cumulative_cache_write_tokens": 0,
        "cumulative_reasoning_tokens": 0,
        "cumulative_agent_steps": steps,
        "cumulative_gateway_reported_cost_usd": spend,
        "cumulative_canonical_spend_usd": spend,
    }


def _row(
    *,
    task_id: str,
    loop: int,
    cohort: str,
    success_submission: int | None,
    spend: float,
    steps: int,
    role: str = "anchor",
) -> object:
    checkpoints = []
    final_submission = success_submission or 4
    for submission in range(1, final_submission + 1):
        checkpoints.append(
            _checkpoint(
                submission,
                spend * submission / final_submission,
                max(1, steps * submission // final_submission),
                passed=submission == success_submission,
            )
        )
    return repair_loop_from_mapping(
        {
            "model": role,
            "task_id": task_id,
            "category": "code",
            "size": "small",
            "loop": loop,
            "passed": success_submission is not None,
            "stop_reason": "passed" if success_submission else "verifier_submission_cap",
            "verifier_submissions": final_submission,
            "input_tokens": 100 * final_submission,
            "output_tokens": 10 * final_submission,
            "turns": steps,
            "agent_steps": steps,
            "model_config_id": "mc_anchor" if role == "anchor" else f"mc_{role}",
            "agent_policy_id": "ap_anchor" if role == "anchor" else f"ap_{role}",
            "task_version": f"{task_id}@v1",
            "verifier_hash": f"sha256:{task_id}",
            "environment_image_digest": f"sha256:env-{task_id}",
            "price_sheet_version": "dev-prices-v1",
            "verifier_submission_cap": 16,
            "agent_step_cap": 256,
            "cap_disclosure": "undisclosed",
            "run_metadata": {
                "phase": "permissive_collection",
                "cohort": cohort,
                "require_canonical_spend": True,
            },
            "event_checkpoints": checkpoints,
            "canonical_list_price_equivalent_spend_usd": spend,
        }
    )


class RepairPolicyTests(unittest.TestCase):
    @staticmethod
    def _complete_methodology(*, task_ids: list[str]) -> dict[str, object]:
        return {
            "schema_version": "shallowswe.methodology_spec.v0.1",
            "methodology_spec_id": "test-methodology",
            "task_ids": task_ids,
            "model_roles": {
                "primary_anchor": "mc_anchor",
                "floor_low": "mc_floor_low",
                "floor_strong": "mc_floor_strong",
            },
            "allow_fallbacks": True,
            "permissive_policy": {
                "candidate_verifier_submission_caps": [2, 4, 6],
                "candidate_agent_step_caps": [32, 64, 128],
                "budget_bands_usd": [0.05, 0.10, 0.20],
            },
            "selection_policy": {
                "success_capture_target": 0.99,
                "reported_budget_coverage_targets": [0.75, 0.9, 1.0],
                "selected_budget_check_coverage_target": 0.75,
                "max_budget_band_bumps": 1,
            },
            "sampling": {
                "permissive_collection": {
                    "anchor_proposal_per_task": 4,
                    "anchor_budget_check_per_task": 2,
                    "each_floor_per_task": 3,
                }
            },
        }

    def test_selects_smallest_caps_and_applies_at_most_one_budget_bump(self) -> None:
        rows = []
        proposal_spend = [0.04, 0.05, 0.08, 0.09]
        check_spend = [0.11, 0.12]
        for loop, spend in enumerate(proposal_spend):
            rows.append(
                _row(
                    task_id="task-a",
                    loop=loop,
                    cohort="budget_proposal",
                    success_submission=2 if loop == 0 else 1,
                    spend=spend,
                    steps=20,
                )
            )
        for loop, spend in enumerate(check_spend, start=4):
            rows.append(
                _row(
                    task_id="task-a",
                    loop=loop,
                    cohort="budget_check",
                    success_submission=1,
                    spend=spend,
                    steps=20,
                )
            )
        for role, successes in (("floor_low", [None, 1, None]), ("floor_strong", [1, 1, 1])):
            for loop, success in enumerate(successes):
                rows.append(
                    _row(
                        task_id="task-a",
                        loop=loop,
                        cohort="floor_panel",
                        success_submission=success,
                        spend=0.03,
                        steps=10,
                        role=role,
                    )
                )

        methodology = {
            "schema_version": "shallowswe.methodology_spec.v0.1",
            "methodology_spec_id": "test-methodology",
            "model_roles": {
                "primary_anchor": "mc_anchor",
                "floor_low": "mc_floor_low",
                "floor_strong": "mc_floor_strong",
            },
            "allow_fallbacks": True,
            "permissive_policy": {
                "candidate_verifier_submission_caps": [2, 4, 6],
                "candidate_agent_step_caps": [32, 64, 128],
                "budget_bands_usd": [0.05, 0.10, 0.20],
            },
            "selection_policy": {
                "success_capture_target": 0.99,
                "reported_budget_coverage_targets": [0.75, 0.9, 1.0],
                "selected_budget_check_coverage_target": 0.75,
                "max_budget_band_bumps": 1,
            },
        }

        report = build_repair_policy(rows, methodology)

        self.assertEqual(report["policy_status"], "analysis_output_not_execution_authority")
        self.assertEqual(report["selected_policy"]["verifier_submission_cap"], 2)
        self.assertEqual(report["selected_policy"]["agent_step_cap"], 32)
        budget = report["task_budgets"][0]
        self.assertEqual(budget["proposal_budget_usd"], 0.10)
        self.assertEqual(budget["selected_budget_usd"], 0.20)
        self.assertEqual(budget["budget_band_bumps"], 1)
        self.assertTrue(budget["budget_check_passed"])
        pressure = report["pressure_diagnostics"][0]
        self.assertAlmostEqual(pressure["floor_first_submit_rate_min"], 1 / 3)
        self.assertAlmostEqual(pressure["floor_first_submit_rate_max"], 1.0)

    def test_rejects_an_incomplete_permissive_matrix(self) -> None:
        rows = [
            _row(
                task_id="task-a",
                loop=loop,
                cohort="budget_proposal" if loop < 4 else "budget_check",
                success_submission=1,
                spend=0.04,
                steps=20,
            )
            for loop in range(6)
        ]
        for role in ("floor_low", "floor_strong"):
            for loop in range(3):
                rows.append(
                    _row(
                        task_id="task-a",
                        loop=loop,
                        cohort="floor_panel",
                        success_submission=1,
                        spend=0.03,
                        steps=10,
                        role=role,
                    )
                )

        with self.assertRaisesRegex(ValueError, "incomplete permissive matrix"):
            build_repair_policy(
                rows[:-1],
                self._complete_methodology(task_ids=["task-a"]),
            )

    def test_declared_fallbacks_keep_the_pipeline_runnable(self) -> None:
        rows = []
        for loop in range(6):
            rows.append(
                _row(
                    task_id="task-a",
                    loop=loop,
                    cohort="budget_proposal" if loop < 4 else "budget_check",
                    success_submission=None,
                    spend=0.30,
                    steps=200,
                )
            )
        for role in ("floor_low", "floor_strong"):
            for loop in range(3):
                rows.append(
                    _row(
                        task_id="task-a",
                        loop=loop,
                        cohort="floor_panel",
                        success_submission=None,
                        spend=0.30,
                        steps=200,
                        role=role,
                    )
                )

        report = build_repair_policy(
            rows,
            self._complete_methodology(task_ids=["task-a"]),
        )

        self.assertEqual(report["selected_policy"]["verifier_submission_cap"], 6)
        self.assertEqual(report["selected_policy"]["agent_step_cap"], 128)
        self.assertEqual(
            report["selected_policy"]["verifier_submission_selection_status"],
            "selection_target_unmet",
        )
        self.assertEqual(
            report["selected_policy"]["agent_step_selection_status"],
            "selection_target_unmet",
        )
        self.assertEqual(report["task_budgets"][0]["selected_budget_usd"], 0.20)
        self.assertEqual(report["task_budgets"][0]["selection_status"], "budget_not_identified")

    def test_rejects_missing_methodology_schema(self) -> None:
        row = _row(
            task_id="task-a",
            loop=0,
            cohort="budget_proposal",
            success_submission=1,
            spend=0.01,
            steps=2,
        )
        with self.assertRaisesRegex(ValueError, "methodology"):
            build_repair_policy([row], {})

    def test_rejects_confirmation_rows_that_do_not_use_exact_selected_policy(self) -> None:
        rows = [
            _row(
                task_id="task-a",
                loop=loop,
                cohort="budget_proposal" if loop < 4 else "budget_check",
                success_submission=1,
                spend=0.04,
                steps=20,
            )
            for loop in range(6)
        ]
        confirmation = [
            replace(
                _row(
                    task_id="task-a",
                    loop=loop,
                    cohort="fresh_confirmation",
                    success_submission=1,
                    spend=0.04,
                    steps=20,
                ),
                run_metadata={
                    "phase": "anchor_confirmation",
                    "cohort": "fresh_confirmation",
                    "require_canonical_spend": True,
                },
                verifier_submission_cap=2,
                agent_step_cap=64,
                reference_task_budget_usd=0.05,
            )
            for loop in range(8)
        ]
        methodology = {
            "schema_version": "shallowswe.methodology_spec.v0.1",
            "methodology_spec_id": "test-methodology",
            "model_roles": {"primary_anchor": "mc_anchor"},
            "allow_fallbacks": True,
            "permissive_policy": {
                "candidate_verifier_submission_caps": [2, 4],
                "candidate_agent_step_caps": [32, 64],
                "budget_bands_usd": [0.05, 0.10],
            },
            "selection_policy": {
                "success_capture_target": 0.99,
                "reported_budget_coverage_targets": [0.75, 0.9, 1.0],
                "selected_budget_check_coverage_target": 0.75,
                "max_budget_band_bumps": 1,
                "confirmation_minimum_successes": 7,
                "confirmation_attempts": 8,
            },
        }

        with self.assertRaisesRegex(ValueError, "selected step guard"):
            build_repair_policy(
                rows + confirmation,
                methodology,
            )


if __name__ == "__main__":
    unittest.main()

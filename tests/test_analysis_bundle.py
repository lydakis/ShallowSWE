from __future__ import annotations

import unittest
from unittest.mock import patch

from shallowswe.analysis_bundle import build_analysis_bundle
from shallowswe.identity import agent_policy_id, model_config_id
from shallowswe.results import repair_loop_from_mapping
from shallowswe.run_spec import run_spec_sha256, trajectory_id


class AnalysisBundleTests(unittest.TestCase):
    def test_selector_is_exogenous_and_metadata_driven(self) -> None:
        rows = [
            repair_loop_from_mapping(
                {
                    "model": "model",
                    "task_id": "task-a",
                    "category": "code",
                    "size": "small",
                    "loop": seed,
                    "passed": True,
                    "stop_reason": "passed",
                    "verifier_submissions": 1,
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "turns": 1,
                    "model_config_id": "model-id",
                    "agent_policy_id": "agent-id",
                    "run_metadata": {"phase": phase},
                    "actual_model_spend_usd": 0.01,
                }
            )
            for seed, phase in enumerate(("score", "calibrate"))
        ]
        methodology = {
            "schema_version": "shallowswe.methodology_spec.v0.1",
            "methodology_spec_id": "analysis-test",
            "row_selector": {"metadata.phase": "score"},
            "group_by": ["model_config_id", "agent_policy_id"],
        }

        report = build_analysis_bundle(rows, methodology)

        self.assertEqual(report["selected_rows"], 1)
        self.assertEqual(len(report["aggregate"]), 1)
        self.assertTrue(report["analysis_bundle_sha256"].startswith("sha256:"))

    def test_binds_complete_scoring_matrix_and_separate_repair_policy_rows(self) -> None:
        scoring_spec = _scoring_run_spec()
        scoring = _scoring_row(scoring_spec, seed=0)
        permissive = _permissive_row()

        with patch("shallowswe.analysis_bundle.build_repair_policy") as build_policy:
            build_policy.return_value = {
                "selected": True,
                "repair_policy_sha256": "sha256:policy",
            }
            report = build_analysis_bundle(
                [scoring, permissive],
                _methodology(),
                scoring_run_spec=scoring_spec,
            )

        policy_rows = list(build_policy.call_args.args[0])
        self.assertEqual(report["selected_rows"], 1)
        self.assertEqual(report["repair_policy_selected_rows"], 1)
        self.assertEqual(report["scoring_run_spec_id"], "scoring-v1")
        self.assertEqual(
            report["scoring_run_spec_sha256"],
            scoring_spec["run_spec_sha256"],
        )
        self.assertEqual(report["replacement_costs_sha256"], "sha256:replacement")
        self.assertEqual(policy_rows[0].run_metadata, {"phase": "permissive_collection"})

    def test_rejects_an_incomplete_scoring_matrix(self) -> None:
        scoring_spec = _scoring_run_spec(seeds=[0, 1])

        with self.assertRaisesRegex(ValueError, "incomplete scoring matrix"):
            build_analysis_bundle(
                [_scoring_row(scoring_spec, seed=0)],
                _methodology(),
                scoring_run_spec=scoring_spec,
            )

    def test_rejects_duplicate_scoring_trajectories(self) -> None:
        scoring_spec = _scoring_run_spec()
        row = _scoring_row(scoring_spec, seed=0)

        with self.assertRaisesRegex(ValueError, "duplicate scoring trajectory"):
            build_analysis_bundle(
                [row, row],
                _methodology(),
                scoring_run_spec=scoring_spec,
            )

    def test_rejects_rows_from_a_different_scoring_run_spec(self) -> None:
        scoring_spec = _scoring_run_spec()
        row = _scoring_row(scoring_spec, seed=0, run_spec_id="scoring-v2")

        with self.assertRaisesRegex(ValueError, "exact scoring RunSpec"):
            build_analysis_bundle(
                [row],
                _methodology(),
                scoring_run_spec=scoring_spec,
            )

    def test_rejects_rows_from_a_different_resolved_model(self) -> None:
        scoring_spec = _scoring_run_spec()
        row = _scoring_row(
            scoring_spec,
            seed=0,
            resolved_model="unexpected-model",
        )

        with self.assertRaisesRegex(ValueError, "execution identity"):
            build_analysis_bundle(
                [row],
                _methodology(),
                scoring_run_spec=scoring_spec,
            )

    def test_rejects_scoring_rows_from_a_different_repair_policy(self) -> None:
        scoring_spec = _scoring_run_spec(repair_policy_hash="sha256:stale")
        scoring = _scoring_row(
            scoring_spec,
            seed=0,
            repair_policy_hash="sha256:stale",
        )

        with patch(
            "shallowswe.analysis_bundle.build_repair_policy",
            return_value={"repair_policy_sha256": "sha256:current"},
        ), self.assertRaisesRegex(ValueError, "repair policy"):
            build_analysis_bundle(
                [scoring, _permissive_row()],
                _methodology(),
                scoring_run_spec=scoring_spec,
            )

    def test_rejects_scoring_rows_from_multiple_replacement_cost_artifacts(self) -> None:
        scoring_spec = _scoring_run_spec(seeds=[0, 1])
        rows = [
            _scoring_row(
                scoring_spec,
                seed=seed,
                replacement_costs_hash=f"sha256:replacement-{seed}",
            )
            for seed in range(2)
        ]
        rows.append(_permissive_row())

        with patch(
            "shallowswe.analysis_bundle.build_repair_policy",
            return_value={"repair_policy_sha256": "sha256:policy"},
        ), self.assertRaisesRegex(ValueError, "exact scoring RunSpec"):
            build_analysis_bundle(
                rows,
                _methodology(),
                scoring_run_spec=scoring_spec,
            )

    def test_requires_scoring_run_spec_for_final_candidate_analysis(self) -> None:
        scoring_spec = _scoring_run_spec()

        with self.assertRaisesRegex(ValueError, "scoring RunSpec is required"):
            build_analysis_bundle(
                [_scoring_row(scoring_spec, seed=0)],
                _methodology(),
            )


def _methodology() -> dict[str, object]:
    return {
        "schema_version": "shallowswe.methodology_spec.v0.1",
        "methodology_spec_id": "analysis-test",
        "row_selector": {"metadata.phase": "candidate_scoring"},
        "repair_policy_row_selector": {"metadata.phase": "permissive_collection"},
        "group_by": ["model_config_id", "agent_policy_id"],
        "select_repair_policy": True,
    }


def _scoring_run_spec(
    *,
    seeds: list[int] | None = None,
    repair_policy_hash: str = "sha256:policy",
) -> dict[str, object]:
    model = {
        "requested_model": "model",
        "expected_resolved_model": "model",
        "provider_route": "kaggle_model_proxy",
        "reasoning_effort": "low",
        "sampling_config": {"temperature": 0.0},
    }
    policy = {"runner": "kaggle", "agent": "mini-swe-agent"}
    model_id = model_config_id(model)
    policy_id = agent_policy_id(policy)
    spec: dict[str, object] = {
        "schema_version": "shallowswe.run_spec.v0.1",
        "run_spec_id": "scoring-v1",
        "experiment_id": "analysis-experiment",
        "task_suite_version": "analysis-suite-v1",
        "model_configs": [{"model_config_id": model_id, "canonical": model}],
        "agent_policies": [{"agent_policy_id": policy_id, "canonical": policy}],
        "units": [
            {
                "run_unit_id": "score-candidate-task-a",
                "runner": "kaggle",
                "model_config_id": model_id,
                "agent_policy_id": policy_id,
                "task_ids": ["task-a"],
                "rollout_seeds": list(seeds or [0]),
                "limits": {
                    "verifier_submissions": 4,
                    "agent_steps": 64,
                    "dollar_usd": 0.05,
                    "wall_time_seconds": 2400,
                },
                "accounting": {
                    "reference_task_budget_usd": 0.05,
                    "required_price_sheet_version": "prices-v1",
                    "reference_budget_version": repair_policy_hash,
                    "reference_anchor_replacement_cost_usd": 0.02,
                    "primary_anchor_model_config_id": "anchor-id",
                    "pressure_band": "low",
                    "expected_task_version": "task-a@v1",
                    "expected_verifier_hash": "sha256:verifier",
                    "expected_environment_image_digest": "sha256:environment",
                },
                "metadata": {
                    "phase": "candidate_scoring",
                    "repair_policy_sha256": repair_policy_hash,
                    "replacement_costs_sha256": "sha256:replacement",
                },
            }
        ],
    }
    spec["run_spec_sha256"] = run_spec_sha256(spec)
    return spec


def _scoring_row(
    spec: dict[str, object],
    *,
    seed: int,
    run_spec_id: str | None = None,
    resolved_model: str = "model",
    repair_policy_hash: str = "sha256:policy",
    replacement_costs_hash: str = "sha256:replacement",
) -> object:
    unit = spec["units"][0]  # type: ignore[index]
    model_entry = spec["model_configs"][0]  # type: ignore[index]
    policy_entry = spec["agent_policies"][0]  # type: ignore[index]
    return repair_loop_from_mapping(
        {
            "model": "model",
            "task_id": "task-a",
            "category": "code",
            "size": "small",
            "loop": seed,
            "seed": seed,
            "passed": True,
            "stop_reason": "passed",
            "verifier_submissions": 1,
            "input_tokens": 10,
            "output_tokens": 2,
            "turns": 1,
            "agent_steps": 1,
            "requested_model": "model",
            "resolved_model": resolved_model,
            "provider_route": "kaggle_model_proxy",
            "reasoning_effort": "low",
            "temperature": 0.0,
            "model_config_id": unit["model_config_id"],  # type: ignore[index]
            "model_config_canonical_json": model_entry["canonical"],  # type: ignore[index]
            "agent_policy_id": unit["agent_policy_id"],  # type: ignore[index]
            "agent_policy_canonical_json": policy_entry["canonical"],  # type: ignore[index]
            "experiment_id": spec["experiment_id"],
            "run_spec_id": run_spec_id or spec["run_spec_id"],
            "run_unit_id": unit["run_unit_id"],  # type: ignore[index]
            "trajectory_id": trajectory_id(
                spec,  # type: ignore[arg-type]
                unit,  # type: ignore[arg-type]
                task_id="task-a",
                rollout_seed=seed,
            ),
            "task_version": "task-a@v1",
            "task_suite_version": spec["task_suite_version"],
            "verifier_hash": "sha256:verifier",
            "environment_image_digest": "sha256:environment",
            "price_sheet_version": "prices-v1",
            "verifier_submission_cap": 4,
            "agent_step_cap": 64,
            "canonical_list_price_equivalent_spend_usd": 0.01,
            "reference_task_budget_usd": 0.05,
            "reference_budget_version": repair_policy_hash,
            "reference_anchor_replacement_cost_usd": 0.02,
            "primary_anchor_model_config_id": "anchor-id",
            "pressure_band": "low",
            "event_checkpoints": [],
            "run_metadata": {
                "phase": "candidate_scoring",
                "repair_policy_sha256": repair_policy_hash,
                "replacement_costs_sha256": replacement_costs_hash,
            },
        }
    )


def _permissive_row() -> object:
    return repair_loop_from_mapping(
        {
            "model": "anchor",
            "task_id": "task-a",
            "category": "code",
            "size": "small",
            "loop": 100,
            "passed": True,
            "stop_reason": "passed",
            "verifier_submissions": 1,
            "input_tokens": 10,
            "output_tokens": 2,
            "turns": 1,
            "run_metadata": {"phase": "permissive_collection"},
        }
    )


if __name__ == "__main__":
    unittest.main()

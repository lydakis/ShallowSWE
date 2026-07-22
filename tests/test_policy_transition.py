from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import unittest

from shallowswe.cli import main
from shallowswe.identity import agent_policy_id, canonical_json, model_config_id
from shallowswe.policy_transition import (
    build_anchor_replacement_costs,
    build_confirmation_run_spec,
    build_scoring_run_spec,
    write_json_artifact,
)
from shallowswe.results import repair_loop_from_mapping
from shallowswe.run_spec import run_spec_sha256, validate_run_spec


class PolicyTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = _model("gpt-anchor", "high")
        self.candidate = _model("gpt-candidate", "low")
        self.policy = {"runner": "kaggle", "agent": "mini-swe-agent"}
        self.anchor_id = model_config_id(self.anchor)
        self.candidate_id = model_config_id(self.candidate)
        self.policy_id = agent_policy_id(self.policy)
        self.base_spec = {
            "schema_version": "shallowswe.run_spec.v0.1",
            "run_spec_id": "permissive-v1",
            "experiment_id": "pipeline-test",
            "task_suite_version": "two-task-v1",
            "model_configs": [
                {"model_config_id": self.anchor_id, "canonical": self.anchor},
            ],
            "agent_policies": [
                {"agent_policy_id": self.policy_id, "canonical": self.policy},
            ],
            "units": [
                {
                    "run_unit_id": "permissive-anchor",
                    "runner": "kaggle",
                    "kaggle_task_name": "permissive-anchor",
                    "model_config_id": self.anchor_id,
                    "agent_policy_id": self.policy_id,
                    "task_ids": ["task-a", "task-b"],
                    "rollout_seeds": [2000],
                    "limits": {
                        "verifier_submissions": 16,
                        "agent_steps": 256,
                        "dollar_usd": 5.0,
                        "wall_time_seconds": 2400,
                    },
                    "metadata": {"phase": "permissive_collection"},
                }
            ],
        }
        self.repair_policy = {
            "schema_version": "shallowswe.repair_policy.v0.1",
            "methodology_spec_id": "methodology-v1",
            "price_sheet_version": "prices-v1",
            "selected_policy": {
                "verifier_submission_cap": 4,
                "agent_step_cap": 64,
                "cap_disclosure": "undisclosed",
            },
            "task_budgets": [
                {
                    "task_id": "task-a",
                    "selected_budget_usd": 0.05,
                    "proposal_budget_usd": 0.05,
                    "budget_band_bumps": 0,
                    "selection_status": "budget_confirmed",
                },
                {
                    "task_id": "task-b",
                    "selected_budget_usd": 0.10,
                    "proposal_budget_usd": 0.05,
                    "budget_band_bumps": 1,
                    "selection_status": "budget_confirmed",
                },
            ],
            "pressure_taxonomies": {
                "three_band": {
                    "assignments": {"task-a": "low", "task-b": "medium"},
                }
            },
            "task_contracts": [
                _task_contract("task-a"),
                _task_contract("task-b"),
            ],
        }
        self.repair_policy["repair_policy_sha256"] = _content_hash(self.repair_policy)
        self.methodology = {
            "schema_version": "shallowswe.methodology_spec.v0.1",
            "methodology_spec_id": "methodology-v1",
            "task_ids": ["task-a", "task-b"],
            "model_roles": {"primary_anchor": self.anchor_id},
            "selection_policy": {
                "confirmation_minimum_successes": 7,
                "confirmation_attempts": 8,
                "pressure_taxonomy": "three_band",
            },
            "sampling": {
                "anchor_confirmation": {
                    "task_ids": ["task-a", "task-b"],
                    "anchor_per_task": 8,
                }
            },
        }
        self.confirmation_spec = build_confirmation_run_spec(
            self.base_spec,
            self.repair_policy,
            self.methodology,
            run_spec_id="confirmation-v1",
            seed_start=4000,
        )

    def test_materializes_task_specific_confirmation_units(self) -> None:
        spec = build_confirmation_run_spec(
            self.base_spec,
            self.repair_policy,
            self.methodology,
            run_spec_id="confirmation-v1",
            seed_start=4000,
        )

        validate_run_spec(spec)
        self.assertEqual(len(spec["units"]), 2)
        by_task = {unit["task_ids"][0]: unit for unit in spec["units"]}
        self.assertEqual(by_task["task-a"]["rollout_seeds"], list(range(4000, 4008)))
        self.assertEqual(by_task["task-a"]["limits"]["dollar_usd"], 0.05)
        self.assertEqual(
            by_task["task-b"]["accounting"]["reference_task_budget_usd"],
            0.10,
        )
        self.assertEqual(by_task["task-b"]["accounting"]["pressure_band"], "medium")
        self.assertEqual(
            by_task["task-a"]["accounting"]["expected_verifier_hash"],
            "sha256:task-a",
        )

    def test_rejects_confirmation_seeds_reused_from_permissive_collection(self) -> None:
        with self.assertRaisesRegex(ValueError, "overlap permissive calibration"):
            build_confirmation_run_spec(
                self.base_spec,
                self.repair_policy,
                self.methodology,
                run_spec_id="confirmation-v1",
                seed_start=2000,
            )

    def test_rejects_repair_policy_from_another_methodology(self) -> None:
        methodology = deepcopy(self.methodology)
        methodology["methodology_spec_id"] = "methodology-v2"

        with self.assertRaisesRegex(ValueError, "methodology_spec_id"):
            build_confirmation_run_spec(
                self.base_spec,
                self.repair_policy,
                methodology,
                run_spec_id="confirmation-v1",
                seed_start=4000,
            )

    def test_calculates_task_specific_replacement_cost_from_all_confirmation_spend(self) -> None:
        rows = []
        for task_id, budget in (("task-a", 0.05), ("task-b", 0.10)):
            for attempt in range(8):
                passed = not (task_id == "task-b" and attempt == 7)
                rows.append(
                    _confirmation_row(
                        task_id=task_id,
                        loop=4000 + attempt,
                        passed=passed,
                        spend=0.02 if task_id == "task-a" else 0.04,
                        budget=budget,
                        anchor_id=self.anchor_id,
                        policy_id=self.policy_id,
                        repair_policy_hash=str(
                            self.repair_policy["repair_policy_sha256"]
                        ),
                    )
                )

        artifact = build_anchor_replacement_costs(
            rows,
            self.repair_policy,
            self.methodology,
            base_run_spec=self.base_spec,
            confirmation_run_spec=self.confirmation_spec,
        )

        by_task = {row["task_id"]: row for row in artifact["tasks"]}
        self.assertAlmostEqual(by_task["task-a"]["replacement_cost_usd"], 0.02)
        self.assertAlmostEqual(by_task["task-b"]["replacement_cost_usd"], 0.32 / 7)
        self.assertTrue(by_task["task-a"]["confirmed"])
        self.assertTrue(by_task["task-b"]["confirmed"])
        self.assertEqual(by_task["task-a"]["rollout_seeds"], list(range(4000, 4008)))
        self.assertEqual(by_task["task-a"]["verifier_hash"], "sha256:task-a")
        self.assertEqual(
            artifact["confirmation_run_spec_sha256"],
            self.confirmation_spec["run_spec_sha256"],
        )
        self.assertTrue(artifact["replacement_costs_sha256"].startswith("sha256:"))

    def test_accepts_exact_targeted_confirmation_recovery_without_rewriting_identity(self) -> None:
        recovery_spec = deepcopy(self.confirmation_spec)
        original_unit = next(
            unit for unit in recovery_spec["units"] if unit["task_ids"] == ["task-b"]
        )
        original_unit["run_unit_id"] = "anchor-confirmation-task-b-recovery-4007"
        original_unit["kaggle_task_name"] = "confirm-task-b-recovery-4007"
        original_unit["rollout_seeds"] = [4007]
        original_unit["metadata"] = {
            **original_unit["metadata"],
            "supersedes_run_spec_id": "confirmation-v1",
            "supersedes_seed": 4007,
        }
        recovery_spec["run_spec_id"] = "confirmation-recovery-v1"
        recovery_spec["units"] = [original_unit]
        recovery_spec["run_spec_sha256"] = run_spec_sha256(recovery_spec)
        validate_run_spec(recovery_spec)

        rows = []
        for task_id, budget in (("task-a", 0.05), ("task-b", 0.10)):
            for attempt in range(8):
                row = _confirmation_row(
                    task_id=task_id,
                    loop=4000 + attempt,
                    passed=True,
                    spend=0.02 if task_id == "task-a" else 0.04,
                    budget=budget,
                    anchor_id=self.anchor_id,
                    policy_id=self.policy_id,
                    repair_policy_hash=str(self.repair_policy["repair_policy_sha256"]),
                )
                if task_id == "task-b" and attempt == 7:
                    row = replace(
                        row,
                        run_spec_id="confirmation-recovery-v1",
                        run_unit_id="anchor-confirmation-task-b-recovery-4007",
                    )
                rows.append(row)

        artifact = build_anchor_replacement_costs(
            rows,
            self.repair_policy,
            self.methodology,
            base_run_spec=self.base_spec,
            confirmation_run_spec=self.confirmation_spec,
            confirmation_recovery_run_specs=[recovery_spec],
        )

        self.assertEqual(
            artifact["confirmation_recovery_run_specs"],
            [
                {
                    "run_spec_id": "confirmation-recovery-v1",
                    "run_spec_sha256": recovery_spec["run_spec_sha256"],
                }
            ],
        )
        task_b = next(row for row in artifact["tasks"] if row["task_id"] == "task-b")
        self.assertEqual(task_b["attempts"], 8)
        self.assertEqual(task_b["successes"], 8)
        self.assertAlmostEqual(task_b["replacement_cost_usd"], 0.04)

    def test_rejects_targeted_recovery_that_changes_the_frozen_limits(self) -> None:
        recovery_spec = deepcopy(self.confirmation_spec)
        recovery_unit = next(
            unit for unit in recovery_spec["units"] if unit["task_ids"] == ["task-b"]
        )
        recovery_unit["run_unit_id"] = "anchor-confirmation-task-b-recovery-4007"
        recovery_unit["rollout_seeds"] = [4007]
        recovery_unit["limits"]["wall_time_seconds"] = 3600
        recovery_spec["run_spec_id"] = "confirmation-recovery-v1"
        recovery_spec["units"] = [recovery_unit]
        recovery_spec["run_spec_sha256"] = run_spec_sha256(recovery_spec)

        with self.assertRaisesRegex(ValueError, "changes the frozen confirmation contract"):
            build_anchor_replacement_costs(
                [],
                self.repair_policy,
                self.methodology,
                base_run_spec=self.base_spec,
                confirmation_run_spec=self.confirmation_spec,
                confirmation_recovery_run_specs=[recovery_spec],
            )

    def test_rejects_rows_outside_the_exact_confirmation_run_spec(self) -> None:
        rows = [
            _confirmation_row(
                task_id=task_id,
                loop=6000 + attempt,
                passed=True,
                spend=0.02,
                budget=budget,
                anchor_id=self.anchor_id,
                policy_id=self.policy_id,
                repair_policy_hash=str(self.repair_policy["repair_policy_sha256"]),
            )
            for task_id, budget in (("task-a", 0.05), ("task-b", 0.10))
            for attempt in range(8)
        ]

        with self.assertRaisesRegex(ValueError, "exact confirmation RunSpec"):
            build_anchor_replacement_costs(
                rows,
                self.repair_policy,
                self.methodology,
                base_run_spec=self.base_spec,
                confirmation_run_spec=self.confirmation_spec,
            )

    def test_rejects_confirmation_rows_from_a_different_agent_policy(self) -> None:
        rows = [
            replace(
                _confirmation_row(
                    task_id=task_id,
                    loop=4000 + attempt,
                    passed=True,
                    spend=0.02,
                    budget=budget,
                    anchor_id=self.anchor_id,
                    policy_id=self.policy_id,
                    repair_policy_hash=str(
                        self.repair_policy["repair_policy_sha256"]
                    ),
                ),
                agent_policy_id="ap_wrong",
            )
            for task_id, budget in (("task-a", 0.05), ("task-b", 0.10))
            for attempt in range(8)
        ]

        with self.assertRaisesRegex(ValueError, "execution identity"):
            build_anchor_replacement_costs(
                rows,
                self.repair_policy,
                self.methodology,
                base_run_spec=self.base_spec,
                confirmation_run_spec=self.confirmation_spec,
            )

    def test_rejects_confirmation_rows_from_a_different_resolved_model(self) -> None:
        rows = [
            replace(
                _confirmation_row(
                    task_id=task_id,
                    loop=4000 + attempt,
                    passed=True,
                    spend=0.02,
                    budget=budget,
                    anchor_id=self.anchor_id,
                    policy_id=self.policy_id,
                    repair_policy_hash=str(
                        self.repair_policy["repair_policy_sha256"]
                    ),
                ),
                resolved_model="unexpected-model",
            )
            for task_id, budget in (("task-a", 0.05), ("task-b", 0.10))
            for attempt in range(8)
        ]

        with self.assertRaisesRegex(ValueError, "execution identity"):
            build_anchor_replacement_costs(
                rows,
                self.repair_policy,
                self.methodology,
                base_run_spec=self.base_spec,
                confirmation_run_spec=self.confirmation_spec,
            )

    def test_rejects_confirmation_results_with_a_changed_task_contract(self) -> None:
        rows = [
            _confirmation_row(
                task_id=task_id,
                loop=4000 + attempt,
                passed=True,
                spend=0.02,
                budget=budget,
                anchor_id=self.anchor_id,
                policy_id=self.policy_id,
                repair_policy_hash=str(self.repair_policy["repair_policy_sha256"]),
                verifier_hash=(
                    "sha256:mutated" if task_id == "task-a" else f"sha256:{task_id}"
                ),
            )
            for task_id, budget in (("task-a", 0.05), ("task-b", 0.10))
            for attempt in range(8)
        ]

        with self.assertRaisesRegex(ValueError, "task contract"):
            build_anchor_replacement_costs(
                rows,
                self.repair_policy,
                self.methodology,
                base_run_spec=self.base_spec,
                confirmation_run_spec=self.confirmation_spec,
            )

    def test_materializes_scoring_units_with_complete_accounting(self) -> None:
        replacement_costs = self._replacement_costs()
        panel = {
            "schema_version": "shallowswe.scoring_panel.v0.1",
            "run_spec_id": "scoring-v1",
            "rollout_seeds": [5000, 5001, 5002],
            "wall_time_seconds": 2400,
            "model_configs": [
                {"model_config_id": self.candidate_id, "canonical": self.candidate},
            ],
            "model_roles": {"candidate": self.candidate_id},
        }

        spec = build_scoring_run_spec(
            self.base_spec,
            panel,
            self.repair_policy,
            replacement_costs,
            self.methodology,
        )

        validate_run_spec(spec)
        self.assertEqual(len(spec["units"]), 2)
        for unit in spec["units"]:
            self.assertEqual(unit["limits"]["verifier_submissions"], 4)
            self.assertEqual(unit["limits"]["agent_steps"], 64)
            self.assertEqual(unit["rollout_seeds"], [5000, 5001, 5002])
            self.assertIsNotNone(
                unit["accounting"]["reference_anchor_replacement_cost_usd"]
            )
            self.assertEqual(unit["metadata"]["phase"], "candidate_scoring")
            task_id = unit["task_ids"][0]
            self.assertEqual(
                unit["accounting"]["expected_task_version"],
                f"{task_id}@v1",
            )

    def test_rejects_scoring_seeds_reused_from_earlier_phases(self) -> None:
        replacement_costs = self._replacement_costs()
        for reused_seed in (2000, 4000):
            panel = self._panel([reused_seed, 5001, 5002])
            with self.subTest(seed=reused_seed), self.assertRaisesRegex(
                ValueError, "overlap"
            ):
                build_scoring_run_spec(
                    self.base_spec,
                    panel,
                    self.repair_policy,
                    replacement_costs,
                    self.methodology,
                )

    def test_rejects_replacement_costs_without_confirmation_seed_provenance(self) -> None:
        replacement_costs = self._replacement_costs()
        first_task = replacement_costs["tasks"][0]
        assert isinstance(first_task, dict)
        first_task.pop("rollout_seeds")
        replacement_costs["replacement_costs_sha256"] = _content_hash(
            replacement_costs,
            hash_field="replacement_costs_sha256",
        )

        with self.assertRaisesRegex(ValueError, "confirmation rollout seeds"):
            build_scoring_run_spec(
                self.base_spec,
                self._panel([5000, 5001, 5002]),
                self.repair_policy,
                replacement_costs,
                self.methodology,
            )

    def test_rejects_replacement_costs_from_another_methodology(self) -> None:
        replacement_costs = self._replacement_costs()
        replacement_costs["methodology_spec_id"] = "methodology-v2"
        replacement_costs["replacement_costs_sha256"] = _content_hash(
            replacement_costs,
            hash_field="replacement_costs_sha256",
        )

        with self.assertRaisesRegex(ValueError, "methodology_spec_id"):
            build_scoring_run_spec(
                self.base_spec,
                self._panel([5000, 5001, 5002]),
                self.repair_policy,
                replacement_costs,
                self.methodology,
            )

    def test_rejects_scoring_when_anchor_confirmation_did_not_accept_task(self) -> None:
        replacement_costs = self._replacement_costs()
        task_b = next(
            row
            for row in replacement_costs["tasks"]
            if isinstance(row, dict) and row["task_id"] == "task-b"
        )
        task_b["successes"] = 6
        task_b["confirmed"] = False
        task_b["replacement_cost_usd"] = 0.32 / 6
        replacement_costs["replacement_costs_sha256"] = _content_hash(
            replacement_costs,
            hash_field="replacement_costs_sha256",
        )
        panel = {
            "schema_version": "shallowswe.scoring_panel.v0.1",
            "run_spec_id": "scoring-v1",
            "rollout_seeds": [5000, 5001, 5002],
            "model_configs": [
                {"model_config_id": self.candidate_id, "canonical": self.candidate},
            ],
            "model_roles": {"candidate": self.candidate_id},
        }

        with self.assertRaisesRegex(ValueError, "did not accept task task-b"):
            build_scoring_run_spec(
                self.base_spec,
                panel,
                self.repair_policy,
                replacement_costs,
                self.methodology,
            )

    def test_shakedown_policy_continues_scoring_with_confirmation_caveat(self) -> None:
        replacement_costs = self._replacement_costs()
        task_b = next(
            row
            for row in replacement_costs["tasks"]
            if isinstance(row, dict) and row["task_id"] == "task-b"
        )
        task_b["successes"] = 6
        task_b["confirmed"] = False
        task_b["replacement_cost_usd"] = 0.32 / 6
        replacement_costs["replacement_costs_sha256"] = _content_hash(
            replacement_costs,
            hash_field="replacement_costs_sha256",
        )
        methodology = deepcopy(self.methodology)
        methodology["selection_policy"]["confirmation_failure_action"] = (
            "continue_with_caveat"
        )

        spec = build_scoring_run_spec(
            self.base_spec,
            self._panel([5000, 5001, 5002]),
            self.repair_policy,
            replacement_costs,
            methodology,
        )

        task_b_units = [
            unit for unit in spec["units"] if unit["task_ids"] == ["task-b"]
        ]
        self.assertEqual(len(task_b_units), 1)
        self.assertEqual(
            task_b_units[0]["metadata"]["anchor_confirmation_status"],
            "confirmation_failed",
        )
        self.assertNotIn(
            "quota_safety_max_output_tokens",
            task_b_units[0]["metadata"],
        )

    def test_scoring_units_record_capped_agent_output_limit(self) -> None:
        base_spec = deepcopy(self.base_spec)
        policy = base_spec["agent_policies"][0]["canonical"]
        policy["max_output_tokens"] = 16_384
        policy["output_token_policy"] = "explicit_kaggle_quota_safety_cap"
        capped_policy_id = agent_policy_id(policy)
        base_spec["agent_policies"][0]["agent_policy_id"] = capped_policy_id
        base_spec["units"][0]["agent_policy_id"] = capped_policy_id
        replacement_costs = self._replacement_costs()
        replacement_costs["confirmation_agent_policy_id"] = capped_policy_id
        replacement_costs["replacement_costs_sha256"] = _content_hash(
            replacement_costs,
            hash_field="replacement_costs_sha256",
        )

        spec = build_scoring_run_spec(
            base_spec,
            self._panel([5000, 5001, 5002]),
            self.repair_policy,
            replacement_costs,
            self.methodology,
        )

        self.assertTrue(spec["units"])
        self.assertTrue(
            all(
                unit["metadata"]["quota_safety_max_output_tokens"] == 16_384
                for unit in spec["units"]
            )
        )

    def test_json_artifacts_are_written_atomically_enough_for_manual_pipeline(self) -> None:
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "artifact.json"
            write_json_artifact(output, {"ok": True})

            self.assertEqual(json.loads(output.read_text()), {"ok": True})

    def _replacement_costs(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": "shallowswe.anchor_replacement_costs.v0.1",
            "methodology_spec_id": "methodology-v1",
            "repair_policy_sha256": self.repair_policy["repair_policy_sha256"],
            "primary_anchor_model_config_id": self.anchor_id,
            "confirmation_run_spec_id": "confirmation-v1",
            "confirmation_run_spec_sha256": self.confirmation_spec[
                "run_spec_sha256"
            ],
            "confirmation_agent_policy_id": self.policy_id,
            "price_sheet_version": "prices-v1",
            "tasks": [
                {
                    **_task_contract("task-a"),
                    "rollout_seeds": list(range(4000, 4008)),
                    "attempts": 8,
                    "successes": 8,
                    "confirmed": True,
                    "replacement_cost_usd": 0.02,
                },
                {
                    **_task_contract("task-b"),
                    "rollout_seeds": list(range(4000, 4008)),
                    "attempts": 8,
                    "successes": 7,
                    "confirmed": True,
                    "replacement_cost_usd": 0.32 / 7,
                },
            ],
        }
        payload["replacement_costs_sha256"] = _content_hash(payload)
        return payload

    def _panel(self, seeds: list[int]) -> dict[str, object]:
        return {
            "schema_version": "shallowswe.scoring_panel.v0.1",
            "run_spec_id": "scoring-v1",
            "rollout_seeds": seeds,
            "model_configs": [
                {"model_config_id": self.candidate_id, "canonical": self.candidate},
            ],
            "model_roles": {"candidate": self.candidate_id},
        }

    def test_cli_materializes_the_complete_policy_transition(self) -> None:
        rows = [
            _confirmation_row(
                task_id=task_id,
                loop=4000 + attempt,
                passed=True,
                spend=0.02 if task_id == "task-a" else 0.04,
                budget=budget,
                anchor_id=self.anchor_id,
                policy_id=self.policy_id,
                repair_policy_hash=str(self.repair_policy["repair_policy_sha256"]),
            )
            for task_id, budget in (("task-a", 0.05), ("task-b", 0.10))
            for attempt in range(8)
        ]
        panel = {
            "schema_version": "shallowswe.scoring_panel.v0.1",
            "run_spec_id": "scoring-v1",
            "rollout_seeds": [5000, 5001, 5002],
            "model_configs": [
                {"model_config_id": self.candidate_id, "canonical": self.candidate},
            ],
            "model_roles": {"candidate": self.candidate_id},
        }
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "base.json"
            policy_path = root / "policy.json"
            methodology_path = root / "methodology.json"
            confirmation_spec_path = root / "confirmation-spec.json"
            confirmation_results_path = root / "confirmation-results.json"
            replacement_path = root / "replacement-costs.json"
            panel_path = root / "panel.json"
            scoring_spec_path = root / "scoring-spec.json"
            for path, payload in (
                (base_path, self.base_spec),
                (policy_path, self.repair_policy),
                (methodology_path, self.methodology),
                (confirmation_results_path, [asdict(row) for row in rows]),
                (panel_path, panel),
            ):
                path.write_text(json.dumps(payload))

            confirmation_spec = _run_cli_json(
                "materialize-confirmation-run-spec",
                str(base_path),
                str(policy_path),
                str(methodology_path),
                str(confirmation_spec_path),
                "--run-spec-id",
                "confirmation-v1",
                "--seed-start",
                "4000",
            )
            replacement_costs = _run_cli_json(
                "calculate-anchor-replacement-costs",
                str(confirmation_results_path),
                str(base_path),
                str(confirmation_spec_path),
                str(policy_path),
                str(methodology_path),
                str(replacement_path),
            )
            scoring_spec = _run_cli_json(
                "materialize-scoring-run-spec",
                str(base_path),
                str(panel_path),
                str(policy_path),
                str(replacement_path),
                str(methodology_path),
                str(scoring_spec_path),
            )

            self.assertEqual(len(confirmation_spec["units"]), 2)
            self.assertEqual(len(replacement_costs["tasks"]), 2)
            self.assertEqual(len(scoring_spec["units"]), 2)
            self.assertTrue(confirmation_spec_path.exists())
            self.assertTrue(replacement_path.exists())
            self.assertTrue(scoring_spec_path.exists())


def _model(name: str, effort: str) -> dict[str, object]:
    return {
        "requested_model": name,
        "expected_resolved_model": name,
        "price_model": f"openai/{name}",
        "provider_route": "kaggle_model_proxy",
        "reasoning_effort": effort,
        "sampling_config": {"temperature": 0.0, "seed_policy": "reserved_replicate"},
    }


def _confirmation_row(
    *,
    task_id: str,
    loop: int,
    passed: bool,
    spend: float,
    budget: float,
    anchor_id: str,
    policy_id: str,
    repair_policy_hash: str,
    verifier_hash: str | None = None,
) -> object:
    model = _model("gpt-anchor", "high")
    policy = {"runner": "kaggle", "agent": "mini-swe-agent"}
    return repair_loop_from_mapping(
        {
            "model": "gpt-anchor",
            "task_id": task_id,
            "category": "code",
            "size": "small",
            "loop": loop,
            "passed": passed,
            "stop_reason": "passed" if passed else "dollar_cap",
            "verifier_submissions": 1,
            "input_tokens": 10,
            "output_tokens": 2,
            "turns": 1,
            "agent_steps": 10,
            "requested_model": "gpt-anchor",
            "resolved_model": "gpt-anchor",
            "reasoning_effort": "high",
            "temperature": 0.0,
            "provider_route": "kaggle_model_proxy",
            "seed": loop,
            "run_spec_id": "confirmation-v1",
            "run_unit_id": f"anchor-confirmation-{task_id}",
            "experiment_id": "pipeline-test",
            "task_suite_version": "two-task-v1",
            "model_config_id": anchor_id,
            "model_config_canonical_json": model,
            "agent_policy_id": policy_id,
            "agent_policy_canonical_json": policy,
            "task_version": f"{task_id}@v1",
            "verifier_hash": verifier_hash or f"sha256:{task_id}",
            "environment_image_digest": f"sha256:env-{task_id}",
            "price_sheet_version": "prices-v1",
            "verifier_submission_cap": 4,
            "agent_step_cap": 64,
            "reference_task_budget_usd": budget,
            "reference_budget_version": repair_policy_hash,
            "primary_anchor_model_config_id": anchor_id,
            "canonical_list_price_equivalent_spend_usd": spend,
            "run_metadata": {"phase": "anchor_confirmation"},
        }
    )


def _task_contract(task_id: str) -> dict[str, str]:
    return {
        "task_id": task_id,
        "task_version": f"{task_id}@v1",
        "verifier_hash": f"sha256:{task_id}",
        "environment_image_digest": f"sha256:env-{task_id}",
    }


def _content_hash(
    payload: dict[str, object],
    *,
    hash_field: str | None = None,
) -> str:
    content = (
        {key: value for key, value in payload.items() if key != hash_field}
        if hash_field
        else payload
    )
    digest = hashlib.sha256(canonical_json(content).encode()).hexdigest()
    return f"sha256:{digest}"


def _run_cli_json(*args: str) -> dict[str, object]:
    output = StringIO()
    with patch("sys.argv", ["shallowswe", *args]), redirect_stdout(output):
        main()
    payload = json.loads(output.getvalue())
    if not isinstance(payload, dict):
        raise AssertionError("CLI did not return a JSON object")
    return payload


if __name__ == "__main__":
    unittest.main()

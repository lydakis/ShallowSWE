from __future__ import annotations

import unittest

from shallowswe.analysis_bundle import build_analysis_bundle
from shallowswe.results import repair_loop_from_mapping


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


if __name__ == "__main__":
    unittest.main()

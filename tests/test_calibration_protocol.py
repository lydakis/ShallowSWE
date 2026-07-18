from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest

from shallowswe.task_metadata import is_official_calibration_status


REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "protocol-governance.md",
    REPO_ROOT / "docs" / "kaggle-runner.md",
    REPO_ROOT / "docs" / "pier-integration.md",
    REPO_ROOT / "docs" / "task-selection-rubric.md",
    REPO_ROOT / "docs" / "task-shape-catalog.md",
    REPO_ROOT / "docs" / "task-sourcing-methodology.md",
    REPO_ROOT / "docs" / "verifier-contract.md",
]


class CalibrationProtocolTests(unittest.TestCase):
    def test_protocol_defines_v2_calibration_contract(self) -> None:
        text = (
            REPO_ROOT / "docs" / "archive" / "legacy-methodology" / "calibration-protocol.md"
        ).read_text()

        for expected in [
            "Pinned ceiling",
            "Dialed floor",
            "Independent ceiling audit",
            "`ceiling_panel`",
            "`floor_probe_panel`",
            "at least `12/16` successful",
            "more than one size band",
            "Single-Model Run Invariant",
            "One-shot runs define task acceptance and size calibration.",
            "bounded repair-loop behavior",
            "`>=75%` is the v1",
            "CPSC = total model spend across scored repair-loop rows / number of successful repair loops",
            "CPSC is computed per `model_config`",
            "Verification failed: missing required artifact.",
            "Verification failed: output mismatch.",
            "dollar cap",
            "verifier-submission cap",
            "agent-step cap",
            "does not use fallback models",
            "never a fallback, cascade, scored substitute",
            "The v1 default floor is 90% scored",
            "no recommended configuration",
            "statistically tied",
            "within 10% of its point-estimate",
            "results replace `N=10`",
            "slice-aggregate only",
            "Task-admission one-shot ceiling gates use `N=16`",
            "Size-calibration floor probes use `N=10`",
            "Published scoring uses `N=10` repair-loop seeds",
            "| Small | Control tasks and high-volume routine work | 70-100% | pre-registered, v1 candidate >=75% |",
            "| Medium | Routine delegated chunks | 30-70% | pre-registered, v1 candidate >=75% |",
            "| Large | Crossover and convergence-pressure tasks | 0-40% | pre-registered, v1 candidate >=75% |",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        self.assertNotIn("routing_margin", text)
        self.assertNotIn("CPSC = mean_cost_per_attempt / pass_rate", text)

    def test_current_docs_do_not_use_old_saturation_gate(self) -> None:
        stale_phrases = [
            "weakest model in the panel passes",
            ">=80% pass saturation gate",
            "at least 80%",
            "T1-T4 difficulty bands",
            "cascade",
            "direct routing frontier",
            "routing frontier",
            "which model should I route",
            "recommended route",
            "cheapest route",
            "measured floor model",
            "For each task/model/seed row",
            "If a row has zero successful repair loops",
            "Rows with zero successful repair loops",
        ]

        for path in CURRENT_DOCS:
            text = path.read_text()
            for phrase in stale_phrases:
                with self.subTest(path=path, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_verifier_feedback_contract_requires_sanitized_classes(self) -> None:
        text = (REPO_ROOT / "docs" / "verifier-contract.md").read_text()

        for expected in [
            "VERIFY_RESULT=passed",
            "VERIFY_RESULT=generic_failure",
            "VERIFY_RESULT=runtime_error",
            "VERIFY_RESULT=missing_required_artifact",
            "VERIFY_RESULT=output_mismatch",
            "VERIFY_RESULT=verifier_infra_error",
            "`verifier_infra_error` is excluded",
            "not from raw hidden",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_calibration_panel_uses_public_size_bands(self) -> None:
        panel = json.loads((REPO_ROOT / "panels" / "shallowswe-calibration-v0.1.json").read_text())

        self.assertEqual(
            set(panel["selection_policy"]["bands"]),
            {"small", "medium", "large"},
        )
        self.assertIn("70-100%", panel["selection_policy"]["bands"]["small"])
        self.assertIn("30-70%", panel["selection_policy"]["bands"]["medium"])
        self.assertIn("0-40%", panel["selection_policy"]["bands"]["large"])
        self.assertIn(">=75%", panel["selection_policy"]["bands"]["small"])
        self.assertIn("floor-probe configuration", panel["selection_policy"]["purpose"])
        self.assertIn("widest pass-rate spread", panel["selection_policy"]["floor_selection_rule"])
        self.assertNotIn("T4", json.dumps(panel))

    def test_ceiling_panel_uses_v2_one_shot_gate(self) -> None:
        panel = json.loads((REPO_ROOT / "panels" / "shallowswe-ceiling-v0.1.json").read_text())
        rule = panel["ceiling_policy"]["admission_rule"]
        rows = {row["id"]: row for row in panel["rows"]}

        self.assertEqual(panel["ceiling_policy"]["primary_row"], "ceiling_gpt_5_5_xhigh")
        self.assertEqual(rows["ceiling_gpt_5_5_xhigh"]["reasoning_effort"], "xhigh")
        self.assertNotIn("ceiling_gpt_5_5_medium", rows)
        self.assertIn("75%", rule)
        self.assertIn("12/16 accepts", rule)
        self.assertIn("11/16 investigates", rule)
        self.assertIn("<=10/16 fixes or evicts", rule)
        self.assertIn("separate one-shot diagnostic", rule)
        self.assertIn("never counts as a fallback success", rule)
        self.assertNotIn("16/16", rule)

    def test_public_spec_names_single_model_scoring_contract(self) -> None:
        spec = (REPO_ROOT / "docs" / "archive" / "legacy-methodology" / "SPEC.md").read_text()
        methodology = (
            REPO_ROOT / "docs" / "archive" / "legacy-methodology" / "methodology.md"
        ).read_text()
        normalized_spec = " ".join(spec.split())

        for expected in [
            "single-model reliability-cost frontier",
            "Every scored run is bound to exactly one `model_config`",
            "CPSC is computed per `model_config`",
            "ShallowSWE does not use model fallback",
            "WeightedCPSC(m)",
            "v1 single-model eligibility floor: **90% scored repair-loop solve rate**",
            "Calibration Panels",
            "`ceiling_panel`",
            "`floor_probe_panel`",
            "task/model_config/seed row",
            "aggregation cell has zero successful repair loops",
            "Solve-rate eligibility is computed over the category/size slice",
            "within 10% of its point-estimate CPSC",
            "Warm-cache and cold-cache pricing are never mixed",
            "Verifier classes",
            "Minimum price-sheet fields",
            "Context exhaustion after meaningful agent progress is scored",
            "model-resolution, provider-dispatch",
            "Published transcripts pass a redaction step",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, normalized_spec)
        self.assertIn("Single-Model Reliability-Cost Frontier", methodology)

    def test_mini_swe_agent_calibration_config_caps_paid_runs(self) -> None:
        text = (REPO_ROOT / "configs" / "mini-swe-agent-calibration.yaml").read_text()

        self.assertIn("step_limit: 20", text)
        self.assertIn("wall_time_limit_seconds: 600", text)


class TaskAuditMetadataTests(unittest.TestCase):
    def test_official_tasks_have_auditable_metadata(self) -> None:
        required = {
            "category",
            "size",
            "language",
            "shape",
            "subtype",
            "family",
            "maintenance_type",
            "domain",
            "source_pattern",
            "repo_origin",
            "requires_test_authoring",
            "expected_engineer_minutes",
            "expected_steps",
            "calibration_status",
            "weakest_model_pass_rate",
            "weakest_model_rollouts",
        }

        for task_toml in sorted((REPO_ROOT / "tasks").glob("*/task.toml")):
            metadata = tomllib.loads(task_toml.read_text())["metadata"]
            if not is_official_calibration_status(metadata.get("calibration_status")):
                continue
            with self.subTest(task=task_toml.parent.name):
                self.assertEqual(required - set(metadata), set())

    def test_official_tasks_record_measured_floor_probe_evidence(self) -> None:
        for task_toml in sorted((REPO_ROOT / "tasks").glob("*/task.toml")):
            metadata = tomllib.loads(task_toml.read_text())["metadata"]
            if not is_official_calibration_status(metadata.get("calibration_status")):
                continue
            with self.subTest(task=task_toml.parent.name):
                self.assertGreaterEqual(metadata["weakest_model_rollouts"], 1)
                self.assertGreaterEqual(metadata["weakest_model_pass_rate"], 0.0)
                self.assertLessEqual(metadata["weakest_model_pass_rate"], 1.0)

    def test_official_tasks_record_structured_calibration_provenance(self) -> None:
        evidence = json.loads(
            (
                REPO_ROOT
                / "results"
                / "shallowswe-floor-probe-n1-v2-postfix-2026-07-04"
                / "task-floor-evidence.json"
            ).read_text()
        )
        floor_evidence_by_task = {
            task["task_id"]: task
            for task in evidence["tasks"]
        }

        for task_toml in sorted((REPO_ROOT / "tasks").glob("*/task.toml")):
            raw = tomllib.loads(task_toml.read_text())
            metadata = raw["metadata"]
            if not is_official_calibration_status(metadata.get("calibration_status")):
                continue
            task_id = task_toml.parent.name
            calibration = raw.get("calibration")

            with self.subTest(task=task_id):
                self.assertIsInstance(calibration, dict)
                self.assertEqual(
                    calibration["calibration_snapshot_id"],
                    "shallowswe-v0.1-candidate-2026-07-04",
                )
                self.assertEqual(calibration["admission_decision"], "candidate_pending_high_n")
                self.assertEqual(
                    calibration["size_assignment_decision"],
                    "candidate_pending_high_n_floor",
                )

                ceiling = calibration["ceiling"]
                self.assertEqual(ceiling["panel"], "shallowswe-ceiling-v0.1")
                self.assertEqual(ceiling["primary_model_config"], "openai/gpt-5.5[extra_high]")
                self.assertEqual(ceiling["one_shot_target_n"], 16)
                self.assertGreaterEqual(ceiling["one_shot_current_n"], 0)
                self.assertLessEqual(ceiling["one_shot_current_n"], 16)
                self.assertGreaterEqual(ceiling["one_shot_passes"], 0)
                self.assertLessEqual(ceiling["one_shot_passes"], ceiling["one_shot_current_n"])
                self.assertNotEqual(ceiling["decision"], "needs_more_rollouts")
                if "medium_smoke_model_config" in ceiling:
                    self.assertEqual(
                        ceiling["medium_smoke_model_config"],
                        "openai/gpt-5.5[medium]",
                    )
                    self.assertEqual(ceiling["medium_smoke_current_n"], 1)
                    self.assertIn(ceiling["medium_smoke_passes"], {0, 1})

                floor = calibration["floor"]
                floor_evidence = floor_evidence_by_task[task_id]
                self.assertEqual(floor["panel"], "shallowswe-calibration-v0.1")
                self.assertEqual(floor["selected_model_config"], "google/gemini-3.5-flash")
                self.assertEqual(floor["one_shot_target_n"], 10)
                self.assertEqual(floor["one_shot_current_n"], 1)
                self.assertEqual(floor["one_shot_passes"], floor_evidence["selected_floor_passes"])
                self.assertEqual(floor["one_shot_pass_rate"], metadata["weakest_model_pass_rate"])
                self.assertEqual(floor["size_band"], metadata["size"])
                self.assertEqual(floor["decision"], "needs_high_n_confirmation")

    def test_task_detail_doc_covers_every_official_task(self) -> None:
        detail_text = (REPO_ROOT / "docs" / "v1-task-verifier-details.md").read_text()

        for task_toml in sorted((REPO_ROOT / "tasks").glob("*/task.toml")):
            metadata = tomllib.loads(task_toml.read_text())["metadata"]
            if not is_official_calibration_status(metadata.get("calibration_status")):
                continue
            task_id = task_toml.parent.name
            with self.subTest(task=task_id):
                self.assertIn(f"### `{task_id}`", detail_text)

    def test_each_task_detail_explains_verifier_strictness_and_shortcuts(self) -> None:
        detail_text = (REPO_ROOT / "docs" / "v1-task-verifier-details.md").read_text()
        sections = [
            section
            for section in detail_text.split("\n### `")
            if section and not section.startswith("#")
        ]

        self.assertEqual(len(sections), 36)
        for section in sections:
            task_id = section.split("`", 1)[0]
            with self.subTest(task=task_id):
                self.assertIn("Verifier:", section)
                self.assertIn("Why strict:", section)
                self.assertIn("Shortcut that fails:", section)

    def test_script_based_tasks_rerun_on_hidden_inputs(self) -> None:
        for instruction in sorted((REPO_ROOT / "tasks").glob("*/instruction.md")):
            task_dir = instruction.parent
            metadata = tomllib.loads((task_dir / "task.toml").read_text())["metadata"]
            if not is_official_calibration_status(metadata.get("calibration_status")):
                continue

            prompt = instruction.read_text()
            verifier = (task_dir / "tests" / "test.sh").read_text()
            solution = (task_dir / "solution" / "solve.sh").read_text()

            if "scripts/build_outputs.py" in prompt:
                with self.subTest(task=task_dir.name, script="build_outputs.py"):
                    self.assertIn("scripts/build_outputs.py", solution)
                    self.assertIn("copy_script_to_hidden", verifier)
                    self.assertIn("build_outputs.py", verifier)

            if "scripts/apply_task.py" in prompt:
                with self.subTest(task=task_dir.name, script="apply_task.py"):
                    self.assertIn("scripts/apply_task.py", solution)
                    self.assertRegex(
                        verifier,
                        r"copy_script_to_(hidden|fresh_root)",
                    )
                    self.assertIn("apply_task.py", verifier)


if __name__ == "__main__":
    unittest.main()

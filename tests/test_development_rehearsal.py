from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.development_rehearsal import run_development_rehearsal


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "configs" / "shallowswe-six-task-pilot-v0.3.json"


class DevelopmentRehearsalTests(unittest.TestCase):
    def test_runs_full_development_only_vertical_slice(self) -> None:
        with TemporaryDirectory() as tmp:
            report = run_development_rehearsal(MANIFEST, Path(tmp))

            self.assertTrue(report["valid"])
            self.assertEqual(report["evidence_class"], "development_dry_run")
            self.assertEqual(report["release_class"], "development_dry_run")
            self.assertEqual(
                report["scripted_stop_reasons"],
                {
                    "dollar_cap": 1,
                    "passed": 2,
                    "runner_exception": 1,
                    "agent_step_cap": 1,
                    "verifier_submission_cap": 1,
                },
            )
            self.assertEqual(report["stage4_policy_status"], "development_proposal")
            self.assertEqual(report["confirmation_check"], "rejected_6_of_8_as_expected")
            self.assertEqual(report["zero_success_cells"], 1)
            self.assertEqual(report["underfilled_workload_cells"], 6)
            self.assertEqual(report["official_launch_guard"], "blocked_as_expected")
            self.assertEqual(report["mixed_evidence_guard"], "rejected_as_expected")
            for filename in (
                "repair-loop-results.json",
                "stage4-policy.json",
                "workload-index.json",
                "rehearsal-report.json",
            ):
                self.assertTrue((Path(tmp) / filename).is_file())
            persisted = json.loads((Path(tmp) / "rehearsal-report.json").read_text())
            self.assertTrue(persisted["valid"])


if __name__ == "__main__":
    unittest.main()

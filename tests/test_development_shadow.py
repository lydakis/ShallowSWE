from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.development_shadow import (
    audit_development_shadow_plan,
    build_development_shadow_plan,
    write_development_shadow_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "configs" / "shallowswe-six-task-pilot-v0.3.json"


class DevelopmentShadowTests(unittest.TestCase):
    def test_builds_disjoint_kaggle_shadow_without_official_evidence(self) -> None:
        schedule, launch_plan = build_development_shadow_plan(MANIFEST)

        self.assertEqual(schedule["plan_class"], "development_shadow")
        self.assertEqual(schedule["trajectory_count"], 190)
        self.assertEqual(
            schedule["stage_counts"],
            {
                "fresh_anchor_confirmation": 48,
                "kaggle_canary": 16,
                "permissive_collection": 72,
                "preliminary_scoring": 54,
            },
        )
        self.assertEqual(
            {row["evidence_class"] for row in schedule["rows"]},
            {"development_dry_run"},
        )
        self.assertEqual(
            {row["release_class"] for row in schedule["rows"]},
            {"development_dry_run"},
        )
        self.assertEqual(
            {
                row["rollout_seed"] // 1000
                for row in schedule["rows"]
            },
            {5, 6, 7, 8},
        )
        self.assertEqual(launch_plan["plan_class"], "development_shadow")
        self.assertEqual(launch_plan["official_trajectory_count"], 0)
        self.assertEqual(launch_plan["development_trajectory_count"], 190)
        self.assertEqual(
            {
                unit["launch_status"]
                for unit in launch_plan["units"]
                if unit["stage"] == "kaggle_canary"
            },
            {"development_ready"},
        )
        self.assertEqual(
            {
                unit["launch_status"]
                for unit in launch_plan["units"]
                if unit["stage"] == "permissive_collection"
            },
            {"blocked_by_development_canary"},
        )
        confirmation = [
            row
            for row in schedule["rows"]
            if row["stage"] == "fresh_anchor_confirmation"
        ]
        self.assertEqual({row["task_id"] for row in confirmation}, set(schedule["task_ids"]))
        scoring = [row for row in schedule["rows"] if row["stage"] == "preliminary_scoring"]
        self.assertEqual(
            {row["model_role"] for row in scoring},
            {"candidate_gemini", "candidate_luna", "candidate_sol"},
        )
        self.assertEqual(
            {
                unit["launch_status"]
                for unit in launch_plan["units"]
                if unit["stage"] == "preliminary_scoring"
            },
            {"blocked_by_fresh_anchor_confirmation"},
        )
        self.assertTrue(
            all(
                unit["kaggle_task_name"].startswith("shallowswe-development-shadow-v0-1-")
                for unit in launch_plan["units"]
            )
        )

    def test_written_shadow_artifacts_audit_exactly(self) -> None:
        with TemporaryDirectory() as tmp:
            schedule_path = Path(tmp) / "schedule.json"
            launch_path = Path(tmp) / "launch.json"

            write_development_shadow_plan(MANIFEST, schedule_path, launch_path)
            report = audit_development_shadow_plan(MANIFEST, schedule_path, launch_path)

            self.assertTrue(report["valid"])
            payload = json.loads(schedule_path.read_text())
            payload["rows"][0]["evidence_class"] = "official_pilot"
            schedule_path.write_text(json.dumps(payload))
            self.assertFalse(
                audit_development_shadow_plan(MANIFEST, schedule_path, launch_path)["valid"]
            )


if __name__ == "__main__":
    unittest.main()

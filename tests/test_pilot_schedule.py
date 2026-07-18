from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.pilot_schedule import audit_pilot_schedule, build_pilot_schedule, write_pilot_schedule


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "configs" / "shallowswe-six-task-pilot-v0.3.json"


class PilotScheduleTests(unittest.TestCase):
    def test_expands_exact_stage_counts_with_unique_reserved_ids(self) -> None:
        schedule = build_pilot_schedule(MANIFEST)

        self.assertEqual(schedule["trajectory_count"], 178)
        self.assertEqual(
            schedule["stage_counts"],
            {
                "codex_development": 66,
                "fresh_anchor_confirmation": 24,
                "kaggle_canary": 16,
                "permissive_collection": 72,
            },
        )
        trajectory_ids = [row["trajectory_id"] for row in schedule["rows"]]
        self.assertEqual(len(trajectory_ids), len(set(trajectory_ids)))
        confirmation = [
            row for row in schedule["rows"] if row["stage"] == "fresh_anchor_confirmation"
        ]
        self.assertEqual({row["cohort"] for row in confirmation}, {"fresh_confirmation"})
        self.assertEqual(
            {row["task_id"] for row in confirmation},
            {
                "access-log-to-incidents",
                "invoice-multi-source-merge",
                "merge-divergent-config-branches",
            },
        )
        anchor_permissive = [
            row
            for row in schedule["rows"]
            if row["stage"] == "permissive_collection"
            and row["model_role"] == "primary_anchor"
            and row["task_id"] == "env-flags-to-json"
        ]
        self.assertEqual([row["replicate"] for row in anchor_permissive], [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            [row["rollout_seed"] for row in anchor_permissive],
            [3000, 3001, 3002, 3003, 3004, 3005],
        )
        stage_seed_sets = {
            stage: {row["rollout_seed"] for row in schedule["rows"] if row["stage"] == stage}
            for stage in schedule["stage_counts"]
        }
        stages = list(stage_seed_sets)
        for index, stage in enumerate(stages):
            for other in stages[index + 1 :]:
                self.assertTrue(stage_seed_sets[stage].isdisjoint(stage_seed_sets[other]))
        development = [
            row for row in schedule["rows"] if row["stage"] == "codex_development"
        ]
        self.assertEqual({row["evidence_class"] for row in development}, {"development_dry_run"})
        self.assertEqual({row["release_class"] for row in development}, {"development_dry_run"})
        official_model_ids = {
            row["model_config_id"]
            for row in schedule["rows"]
            if row["stage"] != "codex_development"
        }
        self.assertTrue(
            {row["model_config_id"] for row in development}.isdisjoint(official_model_ids)
        )
        official = [row for row in schedule["rows"] if row["stage"] != "codex_development"]
        self.assertEqual({row["release_class"] for row in official}, {"protocol_validation"})
        self.assertEqual(schedule["identity_status"], "frozen")

    def test_written_schedule_audits_against_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "schedule.json"
            write_pilot_schedule(MANIFEST, output)

            report = audit_pilot_schedule(MANIFEST, output)

            self.assertTrue(report["valid"])
            payload = json.loads(output.read_text())
            payload["rows"][0]["replicate"] = 999
            output.write_text(json.dumps(payload))
            self.assertFalse(audit_pilot_schedule(MANIFEST, output)["valid"])


if __name__ == "__main__":
    unittest.main()

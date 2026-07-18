from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import tomllib
import unittest

from shallowswe.routine_review import (
    audit_routine_review_packet,
    build_routine_review_packet,
    import_routine_reviews,
)
from shallowswe.task_quality import ROUTINE_REVIEW_RUBRIC_FIELDS


class RoutineReviewPacketTests(unittest.TestCase):
    def test_blind_packet_and_hash_bound_import(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _write_task(root / "tasks" / "task-a")
            manifest = root / "pilot.json"
            manifest.write_text(
                json.dumps(
                    {
                        "name": "pilot",
                        "task_root": "tasks",
                        "task_ids": ["task-a"],
                    }
                )
            )
            packet = root / "packet"

            build_routine_review_packet(manifest, packet, repo_root=root)

            blind = packet / "tasks" / "task-a" / "blind-review"
            self.assertTrue((blind / "instruction.md").is_file())
            self.assertTrue((blind / "environment" / "fixture.txt").is_file())
            self.assertFalse((blind / "solution").exists())
            self.assertFalse((blind / "tests").exists())
            blind_metadata_text = (blind / "task.toml").read_text()
            blind_metadata = tomllib.loads(blind_metadata_text)
            self.assertEqual(blind_metadata["metadata"]["category"], "code")
            self.assertEqual(
                blind_metadata["metadata"]["calibration_status"],
                "withheld_for_blind_review",
            )
            self.assertNotIn("size", blind_metadata["metadata"])
            self.assertNotIn("expected_engineer_minutes", blind_metadata_text)
            self.assertNotIn("gpt-5.4-mini", blind_metadata_text)
            form = json.loads((packet / "tasks" / "task-a" / "review-form.json").read_text())
            self.assertEqual(
                form["review_instructions"]["rubric_rating_values"],
                ["pass", "revise", "reject"],
            )
            self.assertIn("category_fit", form["rubric"])
            self.assertTrue(form["artifact_hashes"]["task_metadata"].startswith("sha256:"))
            self.assertIn(
                "do not use `accept` as a rubric rating", (packet / "README.md").read_text()
            )
            self.assertIn(
                "Classify category by the requested work product",
                (packet / "README.md").read_text(),
            )
            self.assertFalse(
                audit_routine_review_packet(manifest, packet, repo_root=root)["ready_to_import"]
            )
            initial = audit_routine_review_packet(manifest, packet, repo_root=root)
            self.assertIn(
                "routine_review_incomplete_rubric",
                initial["issues_by_task"]["task-a"],
            )

            form_path = packet / "tasks" / "task-a" / "review-form.json"
            form = json.loads(form_path.read_text())
            form["reviewer"] = {
                "reviewer_id": "engineer-1",
                "qualification": "software engineer",
                "independent_from_task_author": True,
            }
            form["decision"] = "accept"
            form["rubric"] = {
                field: {"rating": "pass", "rationale": f"Reviewed {field}."}
                for field in ROUTINE_REVIEW_RUBRIC_FIELDS
            }
            form_path.write_text(json.dumps(form))

            self.assertTrue(
                audit_routine_review_packet(manifest, packet, repo_root=root)["ready_to_import"]
            )
            imported = import_routine_reviews(
                manifest,
                packet,
                write=True,
                repo_root=root,
            )
            self.assertTrue(imported["ready_to_import"])
            self.assertTrue((task / "quality" / "routine-review.json").is_file())

            original_metadata = (task / "task.toml").read_text()
            (task / "task.toml").write_text(original_metadata + "\n# changed\n")
            stale_metadata = audit_routine_review_packet(manifest, packet, repo_root=root)
            self.assertFalse(stale_metadata["ready_to_import"])
            self.assertIn(
                "routine_review_stale_artifact_hashes",
                stale_metadata["issues_by_task"]["task-a"],
            )
            (task / "task.toml").write_text(original_metadata)

            (task / "environment" / "fixture.txt").write_text("changed\n")
            stale = audit_routine_review_packet(manifest, packet, repo_root=root)
            self.assertFalse(stale["ready_to_import"])
            self.assertIn("routine_review_stale_artifact_hashes", stale["issues_by_task"]["task-a"])


def _write_task(path: Path) -> Path:
    (path / "environment").mkdir(parents=True)
    (path / "environment" / "fixture.txt").write_text("base\n")
    (path / "tests").mkdir()
    (path / "tests" / "test.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (path / "solution").mkdir()
    (path / "solution" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    (path / "quality").mkdir()
    (path / "quality" / "investigator-review.md").write_text("Model-assisted review.\n")
    (path / "instruction.md").write_text("Do the task.\n")
    (path / "task.toml").write_text(
        """[task]
name = "shallowswe/task-a"
description = "Patch normal application behavior."

[metadata]
category = "code"
language = "python"
size = "small"
calibration_status = "candidate"
expected_engineer_minutes = 15

[calibration.floor]
model_config = "openai/gpt-5.4-mini[low]"
pass_rate = 1.0
"""
    )
    return path


if __name__ == "__main__":
    unittest.main()

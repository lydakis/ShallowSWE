from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
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

[metadata]
category = "code"
size = "small"
calibration_status = "candidate"
"""
    )
    return path


if __name__ == "__main__":
    unittest.main()

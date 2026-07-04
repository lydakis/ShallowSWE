from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shallowswe.task_metadata import load_task


class TaskMetadataTests(unittest.TestCase):
    def test_loads_optional_shape_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task"
            task_dir.mkdir()
            (task_dir / "task.toml").write_text(
                """
[task]
name = "shallowswe/example"

[metadata]
category = "transform"
tier = "t2"
language = "python"
shape = "config-migration"
subtype = "fixture"
calibration_status = "candidate"
""".strip()
            )

            task = load_task(task_dir)

        self.assertEqual(task.task_id, "example")
        self.assertEqual(task.category, "artifact")
        self.assertEqual(task.size, "medium")
        self.assertEqual(task.tier, "medium")
        self.assertEqual(task.shape, "config-migration")
        self.assertEqual(task.calibration_status, "candidate")

    def test_accepts_legacy_t4_metadata_as_large_workflow(self) -> None:
        with TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task"
            task_dir.mkdir()
            (task_dir / "task.toml").write_text(
                """
[task]
name = "shallowswe/shelf-edge"

[metadata]
category = "operate"
tier = "t4"
shape = "cross-cutting-rename"
""".strip()
            )

            task = load_task(task_dir)

        self.assertEqual(task.task_id, "shelf-edge")
        self.assertEqual(task.category, "workflow")
        self.assertEqual(task.size, "large")
        self.assertEqual(task.tier, "large")

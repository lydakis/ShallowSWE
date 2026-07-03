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
""".strip()
            )

            task = load_task(task_dir)

        self.assertEqual(task.task_id, "example")
        self.assertEqual(task.category, "transform")
        self.assertEqual(task.tier, "t2")
        self.assertEqual(task.shape, "config-migration")

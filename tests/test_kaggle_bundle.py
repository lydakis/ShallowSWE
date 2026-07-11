from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.kaggle_bundle import (
    export_kaggle_bundle,
    materialize_task_environment,
)


class KaggleBundleTests(unittest.TestCase):
    def test_materializer_uses_canonical_dockerfile_copy_and_generator_steps(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _write_task(root / "tasks" / "generated-task")
            workspace = root / "workspace"

            materialize_task_environment(task, workspace)

            self.assertEqual((workspace / "generated.json").read_text(), '{"ok": true}\n')
            self.assertEqual((workspace / "visible.txt").read_text(), "visible\n")
            self.assertFalse((workspace / "instruction.md").exists())
            self.assertFalse((workspace / "hidden.txt").exists())

    def test_export_separates_agent_bundle_from_hidden_verifier(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_root = root / "tasks"
            _write_task(tasks_root / "generated-task")
            config = root / "mini.yaml"
            config.write_text("agent:\n  system_template: test\n")
            pilot_manifest = root / "pilot.json"
            pilot_manifest.write_text(json.dumps({"name": "pilot"}))
            pilot_schedule = root / "schedule.json"
            pilot_schedule.write_text(json.dumps({"rows": []}))
            pilot_launch_plan = root / "launch-plan.json"
            pilot_launch_plan.write_text(json.dumps({"units": []}))
            price_sheet = root / "prices.json"
            price_sheet.write_text(json.dumps({"models": {}}))
            output = root / "bundle"

            manifest = export_kaggle_bundle(
                tasks_root=tasks_root,
                output_dir=output,
                task_ids=["generated-task"],
                config_file=config,
                pilot_manifest_path=pilot_manifest,
                pilot_schedule_path=pilot_schedule,
                pilot_launch_plan_path=pilot_launch_plan,
                price_sheet_path=price_sheet,
            )

            disk_manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest, disk_manifest)
            self.assertEqual(manifest["schema_version"], "shallowswe.kaggle_bundle.v0.1")
            self.assertEqual(manifest["task_ids"], ["generated-task"])
            task_entry = manifest["tasks"][0]
            self.assertEqual(task_entry["task_id"], "generated-task")
            self.assertTrue(task_entry["source_task_hash"].startswith("sha256:"))
            self.assertTrue(task_entry["environment_hash"].startswith("sha256:"))
            self.assertTrue(task_entry["verifier_hash"].startswith("sha256:"))
            self.assertTrue((output / "tasks" / "generated-task" / "environment").is_dir())
            self.assertTrue((output / "verifiers" / "generated-task" / "test.sh").is_file())
            self.assertTrue((output / "config" / "mini.yaml").is_file())
            self.assertEqual(manifest["pilot_manifest"], "protocol/pilot.json")
            self.assertEqual(manifest["pilot_schedule"], "protocol/schedule.json")
            self.assertEqual(
                manifest["pilot_launch_plan"],
                "protocol/launch-plan.json",
            )
            self.assertEqual(manifest["price_sheet"], "protocol/prices.json")
            self.assertTrue((output / "protocol" / "pilot.json").is_file())
            self.assertFalse((output / "tasks" / "generated-task" / "solution").exists())
            self.assertFalse((output / "tasks" / "generated-task" / "tests").exists())
            materialized = root / "materialized-export"
            materialize_task_environment(
                output / "tasks" / "generated-task",
                materialized,
            )
            self.assertTrue((materialized / "generated.json").is_file())

    def test_unsupported_dockerfile_instruction_fails_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            task = _write_task(Path(tmp) / "task")
            dockerfile = task / "environment" / "Dockerfile"
            dockerfile.write_text(dockerfile.read_text() + "RUN apt-get update\n")

            with self.assertRaisesRegex(ValueError, "unsupported Kaggle Dockerfile instruction"):
                materialize_task_environment(task, Path(tmp) / "workspace")


def _write_task(task: Path) -> Path:
    environment = task / "environment"
    verifier = task / "tests"
    solution = task / "solution"
    environment.mkdir(parents=True)
    verifier.mkdir()
    solution.mkdir()
    (environment / "Dockerfile").write_text(
        """\
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY generate_fixture.py /tmp/generate_fixture.py
RUN python /tmp/generate_fixture.py /app
COPY visible.txt /app/visible.txt
"""
    )
    (environment / "generate_fixture.py").write_text(
        """\
from pathlib import Path
import sys
Path(sys.argv[1], "generated.json").write_text('{"ok": true}\\n')
"""
    )
    (environment / "visible.txt").write_text("visible\n")
    (task / "instruction.md").write_text("Generate the required artifact.\n")
    (task / "task.toml").write_text(
        """\
schema_version = "1.2"

[task]
name = "shallowswe/generated-task"

[metadata]
category = "artifact"
size = "small"

[verifier]
timeout_sec = 120.0
"""
    )
    (verifier / "test.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (verifier / "hidden.txt").write_text("hidden\n")
    (solution / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    return task


if __name__ == "__main__":
    unittest.main()

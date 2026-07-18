from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.identity import agent_policy_id, model_config_id
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
            run_spec = root / "run-spec.json"
            run_spec.write_text(json.dumps(_run_spec()))
            price_sheet = root / "prices.json"
            price_sheet.write_text(json.dumps({"models": {}}))
            output = root / "bundle"

            manifest = export_kaggle_bundle(
                tasks_root=tasks_root,
                output_dir=output,
                task_ids=["generated-task"],
                config_file=config,
                run_spec_path=run_spec,
                price_sheet_path=price_sheet,
            )

            disk_manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest, disk_manifest)
            self.assertEqual(manifest["schema_version"], "shallowswe.kaggle_bundle.v0.2")
            self.assertEqual(manifest["task_ids"], ["generated-task"])
            task_entry = manifest["tasks"][0]
            self.assertEqual(task_entry["task_id"], "generated-task")
            self.assertTrue(task_entry["source_task_hash"].startswith("sha256:"))
            self.assertTrue(task_entry["environment_hash"].startswith("sha256:"))
            self.assertTrue(task_entry["verifier_hash"].startswith("sha256:"))
            self.assertTrue((output / "tasks" / "generated-task" / "environment").is_dir())
            self.assertTrue((output / "verifiers" / "generated-task" / "test.sh").is_file())
            self.assertTrue((output / "config" / "mini.yaml").is_file())
            self.assertEqual(manifest["run_spec"], "run/run-spec.json")
            self.assertTrue(manifest["run_spec_sha256"].startswith("sha256:"))
            self.assertEqual(manifest["price_sheet"], "pricing/prices.json")
            self.assertTrue((output / "run" / "run-spec.json").is_file())
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

    def test_export_rejects_a_run_spec_task_missing_from_the_bundle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_root = root / "tasks"
            _write_task(tasks_root / "generated-task")
            config = root / "mini.yaml"
            config.write_text("agent:\n  system_template: test\n")
            spec = _run_spec()
            spec["units"][0]["task_ids"].append("missing-task")
            run_spec = root / "run-spec.json"
            run_spec.write_text(json.dumps(spec))

            with self.assertRaisesRegex(ValueError, "missing run-spec tasks: missing-task"):
                export_kaggle_bundle(
                    tasks_root=tasks_root,
                    output_dir=root / "bundle",
                    task_ids=["generated-task"],
                    config_file=config,
                    run_spec_path=run_spec,
                )


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


def _run_spec() -> dict[str, object]:
    model = {
        "requested_model": "model-name",
        "expected_resolved_model": "model-name",
        "sampling_config": {"temperature": 0.0},
    }
    policy = {"agent": "mini-swe-agent"}
    model_id = model_config_id(model)
    policy_id = agent_policy_id(policy)
    return {
        "schema_version": "shallowswe.run_spec.v0.1",
        "run_spec_id": "test-run",
        "experiment_id": "test-experiment",
        "task_suite_version": "test-suite",
        "model_configs": [
            {
                "model_config_id": model_id,
                "canonical": model,
            }
        ],
        "agent_policies": [
            {"agent_policy_id": policy_id, "canonical": policy}
        ],
        "units": [
            {
                "run_unit_id": "unit-id",
                "runner": "kaggle",
                "model_config_id": model_id,
                "agent_policy_id": policy_id,
                "task_ids": ["generated-task"],
                "rollout_seeds": [0],
                "limits": {
                    "verifier_submissions": 3,
                    "agent_steps": 20,
                    "wall_time_seconds": 120,
                },
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()

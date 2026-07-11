from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from shallowswe.pilot_freeze import _hash_paths, freeze_pilot_manifest


class PilotFreezeTests(unittest.TestCase):
    def test_hash_paths_accepts_relative_files_with_an_absolute_base(self) -> None:
        with TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            artifact = root / "prices.json"
            artifact.write_text("{}\n")
            relative = artifact.relative_to(Path.cwd())
            self.assertRegex(
                _hash_paths([relative], base=Path.cwd()),
                r"^sha256:[0-9a-f]{64}$",
            )

    def test_refuses_to_write_when_any_gate_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            original = {"name": "pilot", "freeze_artifacts": {"task_hashes": None}}
            manifest.write_text(json.dumps(original))
            with patch(
                "shallowswe.pilot_freeze.build_pilot_freeze_report",
                return_value={
                    "ready_to_freeze": False,
                    "blockers": ["pilot_routine_review_incomplete"],
                },
            ):
                with self.assertRaisesRegex(RuntimeError, "pilot_routine_review_incomplete"):
                    freeze_pilot_manifest(
                        manifest,
                        runner_bundle=Path(tmp) / "bundle",
                        price_sheet=Path(tmp) / "prices.json",
                    )
            self.assertEqual(json.loads(manifest.read_text()), original)

    def test_writes_computed_artifacts_after_all_gates_pass(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps({"name": "pilot", "freeze_artifacts": {}}))
            bundle = Path(tmp) / "bundle"
            (bundle / "protocol").mkdir(parents=True)
            (bundle / "manifest.json").write_text(
                json.dumps({"pilot_manifest": "protocol/pilot.json"})
            )
            (bundle / "protocol" / "pilot.json").write_text(manifest.read_text())
            candidate = {
                "price_sheet": {"path": "prices.json", "sha256": "sha256:price"},
                "task_hashes": {"task": "sha256:task"},
            }
            with patch(
                "shallowswe.pilot_freeze.build_pilot_freeze_report",
                return_value={
                    "ready_to_freeze": True,
                    "blockers": [],
                    "candidate_artifacts": candidate,
                },
            ):
                freeze_pilot_manifest(
                    manifest,
                    runner_bundle=bundle,
                    price_sheet=Path(tmp) / "prices.json",
                )
            self.assertEqual(json.loads(manifest.read_text())["freeze_artifacts"], candidate)
            self.assertEqual(
                (bundle / "protocol" / "pilot.json").read_text(),
                manifest.read_text(),
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from shallowswe.kaggle_task_source import write_bound_kaggle_task_sources


class KaggleTaskSourceTests(unittest.TestCase):
    def test_writes_one_hash_bound_source_per_ready_unit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "runner.py"
            source.write_text(
                'FROZEN_LAUNCH_UNIT_ID: str | None = None\n'
                '@kbench.task(\n    name="shallowswe-repair-loop-v2",\n)\n'
            )
            launch_plan = root / "launch.json"
            launch_plan.write_text(
                json.dumps(
                    {
                        "plan_class": "development_shadow",
                        "units": [
                            {
                                "launch_unit_id": "plu_one",
                                "launch_status": "development_ready",
                                "kaggle_task_name": "shadow-one",
                                "model": "model-one",
                            },
                            {
                                "launch_unit_id": "plu_blocked",
                                "launch_status": "blocked_by_development_canary",
                                "kaggle_task_name": "shadow-blocked",
                                "model": "model-two",
                            },
                        ],
                    }
                )
            )

            report = write_bound_kaggle_task_sources(source, launch_plan, root / "out")

            self.assertEqual(report["source_count"], 1)
            generated = (root / "out" / "shadow-one.py").read_text()
            self.assertIn('FROZEN_LAUNCH_UNIT_ID: str | None = "plu_one"', generated)
            self.assertIn('name="shadow-one"', generated)
            self.assertNotIn("plu_blocked", generated)
            self.assertTrue(report["sources"][0]["sha256"].startswith("sha256:"))

    def test_rejects_source_without_exact_freeze_markers(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "runner.py"
            source.write_text("print('unbound')\n")
            launch = root / "launch.json"
            launch.write_text(json.dumps({"plan_class": "development_shadow", "units": []}))

            with self.assertRaisesRegex(ValueError, "freeze marker"):
                write_bound_kaggle_task_sources(source, launch, root / "out")


if __name__ == "__main__":
    unittest.main()

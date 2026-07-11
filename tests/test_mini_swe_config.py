from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shallowswe.mini_swe_config import (
    effective_scaffold_prompt_hash,
    load_effective_mini_swe_config,
)


class MiniSweConfigTests(unittest.TestCase):
    def test_effective_hash_includes_base_prompts_and_recursive_overrides(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "mini.yaml"
            override = root / "override.yaml"
            base.write_text(
                "agent:\n  system_template: base system\n  instance_template: base task\n"
                "model:\n  observation_template: base observation\n"
                "  format_error_template: base format error\n"
            )
            override.write_text("agent:\n  system_template: shared system\n")

            effective = load_effective_mini_swe_config(
                override,
                base_config_file=base,
            )

            self.assertEqual(effective["agent"]["system_template"], "shared system")
            self.assertEqual(effective["agent"]["instance_template"], "base task")
            self.assertTrue(effective_scaffold_prompt_hash(effective).startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

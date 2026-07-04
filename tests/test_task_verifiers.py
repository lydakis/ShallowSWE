from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class TaskVerifierWrapperTests(unittest.TestCase):
    def test_task_verifiers_propagate_hidden_check_status(self) -> None:
        for verifier in sorted((REPO_ROOT / "tasks").glob("*/tests/test.sh")):
            with self.subTest(verifier=verifier):
                text = verifier.read_text()

                self.assertIn("status=$?", text)
                self.assertIn('exit "$status"', text)


if __name__ == "__main__":
    unittest.main()

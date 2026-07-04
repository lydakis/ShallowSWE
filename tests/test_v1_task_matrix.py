from __future__ import annotations

from collections import Counter
from pathlib import Path
import tomllib
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class V1TaskMatrixTests(unittest.TestCase):
    def test_official_v1_matrix_has_four_tasks_per_category_size_cell(self) -> None:
        rows: list[tuple[str, str, str]] = []
        for task_dir in sorted((REPO_ROOT / "tasks").iterdir()):
            config_path = task_dir / "task.toml"
            if not config_path.exists():
                continue
            with config_path.open("rb") as handle:
                raw = tomllib.load(handle)
            metadata = raw["metadata"]
            if metadata.get("calibration_status") == "smoke":
                continue
            rows.append((metadata["category"], metadata["size"], task_dir.name))

        counts = Counter((category, size) for category, size, _task_id in rows)

        self.assertEqual(len(rows), 36)
        self.assertEqual(
            counts,
            Counter(
                {
                    ("artifact", "large"): 4,
                    ("artifact", "medium"): 4,
                    ("artifact", "small"): 4,
                    ("code", "large"): 4,
                    ("code", "medium"): 4,
                    ("code", "small"): 4,
                    ("workflow", "large"): 4,
                    ("workflow", "medium"): 4,
                    ("workflow", "small"): 4,
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()

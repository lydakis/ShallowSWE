from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from shallowswe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_admission_audit_cli_reports_snapshot_readiness(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "example"
            task_dir.mkdir()
            (task_dir / "environment").mkdir()
            (task_dir / "tests").mkdir()
            (task_dir / "tests" / "test.sh").write_text(
                "#!/usr/bin/env bash\n"
                "python3 -m unittest discover\n"
                "status=$?\n"
                'exit "$status"\n'
            )
            (task_dir / "solution").mkdir()
            (task_dir / "solution" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n")
            (task_dir / "instruction.md").write_text("Do the task.\n")
            (task_dir / "task.toml").write_text(
                """
[task]
name = "shallowswe/example"

[metadata]
category = "code"
size = "small"
calibration_status = "candidate"
""".strip()
            )

            audit = _run_cli_json("admission-audit", str(root))

        self.assertFalse(audit["ready_for_snapshot"])
        self.assertEqual(audit["issue_counts"], {"missing_alternate_solution": 1})

    def test_aggregate_accepts_multiple_price_sheets(self) -> None:
        with TemporaryDirectory() as tmp:
            results_path = Path(tmp) / "results.json"
            results_path.write_text(json.dumps(_mixed_gateway_rows()))

            summaries = _run_cli_json(
                "aggregate",
                str(results_path),
                "--prices",
                str(REPO_ROOT / "prices" / "openrouter-2026-07-03.json"),
                "--prices",
                str(REPO_ROOT / "prices" / "openai-2026-07-03.json"),
            )

        self.assertEqual({row["model_config"] for row in summaries}, {"openai/gpt-5.5", "gpt-5.5"})
        self.assertTrue(all(row["mean_cost_per_attempt"] > 0 for row in summaries))

    def test_workload_index_accepts_multiple_price_sheets(self) -> None:
        with TemporaryDirectory() as tmp:
            results_path = Path(tmp) / "results.json"
            results_path.write_text(json.dumps(_mixed_gateway_rows()))

            index = _run_cli_json(
                "workload-index",
                str(results_path),
                "--prices",
                str(REPO_ROOT / "prices" / "openrouter-2026-07-03.json"),
                "--prices",
                str(REPO_ROOT / "prices" / "openai-2026-07-03.json"),
            )

        models = {model["model_config"]: model for model in index["models"]}
        self.assertEqual(set(models), {"openai/gpt-5.5", "gpt-5.5"})
        self.assertTrue(all(model["basket_cpsc"] for model in models.values()))

    def test_ceiling_gate_cli_reports_one_shot_admission_status(self) -> None:
        with TemporaryDirectory() as tmp:
            results_path = Path(tmp) / "results.json"
            rows = [
                {
                    "model": "ceiling",
                    "task_id": "example",
                    "category": "code",
                    "size": "small",
                    "rollout": rollout,
                    "passed": rollout < 3,
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "turns": 1,
                }
                for rollout in range(4)
            ]
            results_path.write_text(json.dumps(rows))

            report = _run_cli_json(
                "ceiling-gate",
                str(results_path),
                "--pass-threshold",
                "0.75",
                "--target-rollouts",
                "4",
            )

        self.assertEqual(report["schema_version"], "shallowswe.one_shot_ceiling_gate.v0.1")
        self.assertEqual(report["accept_min_passes"], 3)
        self.assertEqual(report["tasks"][0]["decision"], "accept")


def _run_cli_json(*args: str):
    output = StringIO()
    with patch("sys.argv", ["shallowswe", *args]), redirect_stdout(output):
        main()
    return json.loads(output.getvalue())


def _mixed_gateway_rows() -> list[dict[str, object]]:
    return [
        {
            "model": "openai/gpt-5.5",
            "task_id": "example",
            "category": "code",
            "size": "small",
            "rollout": 0,
            "passed": True,
            "input_tokens": 1_000,
            "output_tokens": 10,
            "cache_read_tokens": 0,
            "turns": 1,
            "inference_gateway": "openrouter",
        },
        {
            "model": "gpt-5.5",
            "task_id": "example",
            "category": "code",
            "size": "small",
            "rollout": 0,
            "passed": True,
            "input_tokens": 1_000,
            "output_tokens": 10,
            "cache_read_tokens": 0,
            "turns": 1,
            "inference_gateway": "openai",
        },
    ]


if __name__ == "__main__":
    unittest.main()

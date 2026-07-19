from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import json
import unittest

from shallowswe import cli


class KaggleCliTests(unittest.TestCase):
    def test_kaggle_pack_routes_canonical_paths_to_exporter(self) -> None:
        output = StringIO()
        with (
            patch.object(cli, "export_kaggle_bundle", return_value={"schema_version": "test"})
            as exporter,
            patch(
                "sys.argv",
                [
                    "shallowswe",
                    "kaggle-pack",
                    "/tmp/bundle",
                    "--task-id",
                    "py-normalize-username",
                    "--task-id",
                    "dependency-api-rename",
                ],
            ),
            redirect_stdout(output),
        ):
            cli.main()

        self.assertEqual(json.loads(output.getvalue()), {"schema_version": "test"})
        exporter.assert_called_once()
        kwargs = exporter.call_args.kwargs
        self.assertEqual(kwargs["tasks_root"], Path("tasks"))
        self.assertEqual(
            kwargs["task_ids"],
            ["py-normalize-username", "dependency-api-rename"],
        )
        self.assertEqual(kwargs["output_dir"], Path("/tmp/bundle"))
        self.assertEqual(kwargs["notebook_source"], Path("kaggle/shallowswe_runner.py"))

    def test_select_repair_policy_routes_only_its_declared_paths(self) -> None:
        output = StringIO()
        with (
            patch.object(cli, "write_repair_policy", return_value={"selected": True}) as writer,
            patch(
                "sys.argv",
                [
                    "shallowswe",
                    "select-repair-policy",
                    "/tmp/results.json",
                    "/tmp/methodology.json",
                    "/tmp/policy.json",
                ],
            ),
            redirect_stdout(output),
        ):
            cli.main()

        self.assertEqual(json.loads(output.getvalue()), {"selected": True})
        writer.assert_called_once_with(
            Path("/tmp/results.json"),
            Path("/tmp/methodology.json"),
            Path("/tmp/policy.json"),
        )

    def test_analyze_repair_loops_routes_the_scoring_run_spec(self) -> None:
        output = StringIO()
        with (
            patch.object(cli, "write_analysis_bundle", return_value={"selected_rows": 54})
            as writer,
            patch(
                "sys.argv",
                [
                    "shallowswe",
                    "analyze-repair-loops",
                    "/tmp/results.json",
                    "/tmp/methodology.json",
                    "/tmp/analysis.json",
                    "--scoring-run-spec",
                    "/tmp/scoring.json",
                ],
            ),
            redirect_stdout(output),
        ):
            cli.main()

        self.assertEqual(json.loads(output.getvalue()), {"selected_rows": 54})
        writer.assert_called_once_with(
            Path("/tmp/results.json"),
            Path("/tmp/methodology.json"),
            Path("/tmp/analysis.json"),
            scoring_run_spec_path=Path("/tmp/scoring.json"),
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "export_repair_loop_site_data.py"
SPEC = spec_from_file_location("export_repair_loop_site_data", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
EXPORTER = module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


class ExportRepairLoopSiteDataTests(unittest.TestCase):
    def test_copy_price_sheet_preserves_other_dated_snapshots(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            prices = root / "openrouter-2026-07-09.json"
            public_data = root / "public-data"
            public_data.mkdir()
            prices.write_text('{"effective_date": "2026-07-09"}\n')
            historical = public_data / "prices-openrouter-2026-07-03.json"
            historical.write_text('{"effective_date": "2026-07-03"}\n')

            exported = EXPORTER._copy_price_sheet(prices, public_data)

            self.assertEqual(exported, public_data / "prices-openrouter-2026-07-09.json")
            self.assertEqual(exported.read_text(), prices.read_text())
            self.assertEqual(historical.read_text(), '{"effective_date": "2026-07-03"}\n')

    def test_provenance_summary_flags_task_level_hash_drift(self) -> None:
        rows = [
            _row(
                task_id="task-a",
                repo_commit_sha="aaa",
                price_sheet_version="prices-a",
                verifier_hash="verifier-a",
                environment_image_digest="image-a",
            ),
            _row(
                task_id="task-a",
                repo_commit_sha="bbb",
                price_sheet_version="prices-b",
                verifier_hash="verifier-b",
                environment_image_digest="image-a",
            ),
        ]

        summary = EXPORTER._provenance_summary(rows)

        self.assertTrue(summary["mixed_snapshot"])
        self.assertEqual(summary["state"], "mixed")
        self.assertEqual(summary["repo_commit_shas"], ["aaa", "bbb"])
        self.assertEqual(summary["price_sheet_versions"], ["prices-a", "prices-b"])
        self.assertEqual(summary["runners"], ["pier-private-repair-loop-pilot"])
        self.assertEqual(summary["inference_gateways"], ["openrouter"])
        self.assertEqual(summary["provider_routes"], ["openrouter/anthropic"])
        self.assertEqual(summary["missing_field_counts"], {})
        self.assertEqual(summary["tasks_with_multiple_verifier_hashes"], ["task-a"])
        self.assertEqual(summary["tasks_with_multiple_environment_digests"], [])

    def test_provenance_summary_fails_closed_when_required_fields_are_missing(self) -> None:
        summary = EXPORTER._provenance_summary(
            [
                _row(repo_commit_sha=None, verifier_hash=None),
                _row(
                    price_sheet_version=None,
                    runner=None,
                    runner_version=None,
                    inference_gateway=None,
                    provider_route=None,
                ),
            ]
        )

        self.assertFalse(summary["mixed_snapshot"])
        self.assertEqual(summary["state"], "incomplete")
        self.assertEqual(
            summary["missing_field_counts"],
            {
                "price_sheet_version": 1,
                "repo_commit_sha": 1,
                "inference_gateway": 1,
                "provider_route": 1,
                "runner": 1,
                "runner_version": 1,
                "verifier_hash": 1,
            },
        )
        self.assertEqual(
            EXPORTER._manifest_status(summary),
            "preview_incomplete_provenance",
        )

    def test_complete_provenance_exposes_backend_identity(self) -> None:
        summary = EXPORTER._provenance_summary([_row(), _row(task_id="task-b")])

        self.assertEqual(summary["state"], "complete")
        self.assertEqual(summary["runners"], ["pier-private-repair-loop-pilot"])
        self.assertEqual(summary["runner_versions"], ["runner-sha"])
        self.assertEqual(summary["inference_gateways"], ["openrouter"])
        self.assertEqual(summary["provider_routes"], ["openrouter/anthropic"])
        self.assertEqual(EXPORTER._manifest_runner(summary), "pier-private-repair-loop-pilot")
        self.assertEqual(EXPORTER._manifest_status(summary), "preview_snapshot")


def _row(**overrides: object) -> SimpleNamespace:
    values = {
        "task_id": "task-a",
        "repo_commit_sha": "repo-sha",
        "price_sheet_version": "openrouter-2026-07-09",
        "verifier_hash": "verifier-sha",
        "environment_image_digest": "image-sha",
        "runner": "pier-private-repair-loop-pilot",
        "runner_version": "runner-sha",
        "inference_gateway": "openrouter",
        "provider_route": "openrouter/anthropic",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


if __name__ == "__main__":
    unittest.main()

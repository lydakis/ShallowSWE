from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from shallowswe.cli import main
from shallowswe.task_funnel import audit_task_funnel


class TaskFunnelTests(unittest.TestCase):
    def test_task_funnel_manifest_tracks_authored_and_planned_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            _write_task(tasks / "authored-large", category="code", size="large")
            manifest = _write_manifest(
                root / "funnel.json",
                tasks_root="tasks",
                candidates=[
                    _candidate("CL-1", "authored-large", "code", "large", "authored"),
                    _candidate("CM-1", "planned-medium", "code", "medium", "planned"),
                ],
            )

            report = audit_task_funnel(manifest, repo_root=root)

        self.assertEqual(report["schema_version"], "shallowswe.task_funnel_audit.v0.1")
        self.assertTrue(report["valid"])
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["authoring_status_counts"], {"authored": 1, "planned": 1})
        self.assertEqual(report["tasks_to_author"], ["planned-medium"])
        self.assertEqual(report["candidate_issue_counts"], {})
        self.assertFalse(report["broad_scoring_allowed"])
        self.assertTrue(report["codex_subscription_triage"])

    def test_kept_candidate_requires_formal_ceiling_and_bridge_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            _write_task(tasks / "maybe-medium", category="artifact", size="medium")
            manifest = _write_manifest(
                root / "funnel.json",
                tasks_root="tasks",
                candidates=[
                    {
                        **_candidate("AM-1", "maybe-medium", "artifact", "medium", "authored"),
                        "funnel_bucket": "keep_medium",
                    },
                ],
            )

            report = audit_task_funnel(manifest, repo_root=root)

        self.assertFalse(report["valid"])
        self.assertEqual(
            report["candidate_issue_counts"],
            {
                "kept_without_bridge_validation": 1,
                "kept_without_formal_ceiling": 1,
            },
        )
        self.assertEqual(report["bridge_validation_pending"], ["maybe-medium"])
        self.assertEqual(report["formal_ceiling_pending"], ["maybe-medium"])

    def test_task_funnel_cli_reports_audit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_task(root / "tasks" / "authored-large", category="workflow", size="large")
            manifest = _write_manifest(
                root / "funnel.json",
                tasks_root="tasks",
                candidates=[
                    _candidate("WL-1", "authored-large", "workflow", "large", "authored")
                ],
            )
            output = StringIO()
            with (
                patch("sys.argv", ["shallowswe", "task-funnel", str(manifest)]),
                patch("pathlib.Path.cwd", return_value=root),
                redirect_stdout(output),
            ):
                main()

            report = json.loads(output.getvalue())

        self.assertTrue(report["valid"])
        self.assertEqual(report["manifest"], "test-task-funnel")
        self.assertEqual(report["candidate_count"], 1)


def _write_task(path: Path, *, category: str, size: str) -> None:
    path.mkdir(parents=True)
    (path / "task.toml").write_text(
        f"""
[task]
name = "shallowswe/{path.name}"

[metadata]
category = "{category}"
size = "{size}"
language = "python"
calibration_status = "candidate_probe"
""".strip()
    )


def _candidate(
    slot: str,
    task_id: str,
    category: str,
    size: str,
    authoring_status: str,
) -> dict[str, object]:
    return {
        "slot": slot,
        "task_id": task_id,
        "category": category,
        "size_hypothesis": size,
        "authoring_status": authoring_status,
        "funnel_bucket": "not_triaged",
        "difficulty_levers": ["L1"],
        "codex_triage": {
            "status": "not_run",
            "floor_model_config": "openai/gpt-5.4-mini[low]",
            "medium_smoke_model_config": "openai/gpt-5.5[medium]",
        },
        "formal_ceiling": {
            "status": "not_run",
            "model_config": "openai/gpt-5.5[extra_high]",
            "target_n": 8,
            "pass_threshold": 0.75,
        },
        "bridge_validation": {
            "status": "not_started",
            "harness": "pier/mini-swe-agent",
            "target_n": 2,
        },
        "next_action": "author_or_triage",
    }


def _write_manifest(
    path: Path,
    *,
    tasks_root: str,
    candidates: list[dict[str, object]],
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "shallowswe.task_funnel.v0.1",
                "name": "test-task-funnel",
                "phase": "test",
                "task_root": tasks_root,
                "candidate_target": {"min": 1, "max": 20},
                "low_spend_policy": {
                    "broad_scoring_allowed": False,
                    "codex_subscription_triage": True,
                    "bridge_required_before_official_label": True,
                },
                "candidates": candidates,
            },
            indent=2,
        )
        + "\n"
    )
    return path


if __name__ == "__main__":
    unittest.main()

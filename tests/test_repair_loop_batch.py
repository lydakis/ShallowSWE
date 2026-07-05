from __future__ import annotations

from pathlib import Path
import threading
import tempfile
import time
import unittest

from shallowswe.repair_loop_batch import (
    build_repair_loop_preview_schedule,
    run_repair_loop_preview_batch,
)
from shallowswe.results import RepairLoopResult, dump_repair_loops, load_repair_loops


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "configs" / "shallowswe-repair-loop-preview-n3-18.json"
CONFIG_PATH = REPO_ROOT / "configs" / "mini-swe-agent-repair-loop-preview.yaml"


class RepairLoopBatchTests(unittest.TestCase):
    def test_build_preview_schedule_interleaves_seed_task_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            schedule = build_repair_loop_preview_schedule(
                PLAN_PATH,
                repo_root=REPO_ROOT,
                output_dir=Path(tmp),
                job_name="preview",
            )

        self.assertEqual(len(schedule), 540)
        self.assertEqual(schedule[0].task_id, "env-flags-to-json")
        self.assertEqual(schedule[0].seed, 0)
        self.assertEqual(schedule[0].model_name, "openrouter/anthropic/claude-fable-5")
        self.assertEqual(schedule[0].reasoning_effort, "low")
        self.assertEqual(schedule[9].model_name, "openrouter/moonshotai/kimi-k2.7-code")
        self.assertIsNone(schedule[9].reasoning_effort)
        self.assertEqual(schedule[10].task_id, "extract-error-fields")
        self.assertEqual(schedule[180].seed, 1)

    def test_preview_batch_dry_run_writes_empty_combined_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = run_repair_loop_preview_batch(
                PLAN_PATH,
                repo_root=REPO_ROOT,
                output_dir=output_dir,
                trials_dir=output_dir / "trials",
                mini_swe_agent_source_dir=REPO_ROOT,
                config_file=CONFIG_PATH,
                agent_env={},
                max_rows=2,
                dry_run=True,
            )

            self.assertTrue(report["dry_run"])
            self.assertEqual(report["total_planned_rows"], 2)
            self.assertEqual(report["completed_rows"], 0)
            self.assertEqual(
                load_repair_loops(output_dir / "repair-loop-results.json"),
                [],
            )

    def test_preview_batch_runs_fake_row_and_preserves_model_config_metadata(self) -> None:
        calls = []

        def fake_runner(**kwargs):
            calls.append(kwargs)
            return _result(
                model="placeholder",
                task_id="env-flags-to-json",
                reasoning_effort=None,
                cost=0.25,
            )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = run_repair_loop_preview_batch(
                PLAN_PATH,
                repo_root=REPO_ROOT,
                output_dir=output_dir,
                trials_dir=output_dir / "trials",
                mini_swe_agent_source_dir=REPO_ROOT,
                config_file=CONFIG_PATH,
                agent_env={},
                max_rows=1,
                runner=fake_runner,
            )
            rows = load_repair_loops(output_dir / "repair-loop-results.json")

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model_name"], "openrouter/anthropic/claude-fable-5")
        self.assertEqual(calls[0]["reasoning_effort"], "low")
        self.assertEqual(report["completed_rows"], 1)
        self.assertEqual(rows[0].model, "openrouter/anthropic/claude-fable-5")
        self.assertEqual(rows[0].reasoning_effort, "low")
        self.assertEqual(rows[0].inference_gateway, "openrouter")
        self.assertEqual(rows[0].upstream_provider, "anthropic")
        self.assertEqual(rows[0].model_config, "openrouter/anthropic/claude-fable-5[low]")

    def test_preview_batch_can_run_independent_rows_in_parallel(self) -> None:
        calls = []
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fake_runner(**kwargs):
            nonlocal active, max_active
            with lock:
                calls.append(kwargs)
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return _result(
                model=kwargs["model_name"],
                task_id=kwargs["task_path"].name,
                reasoning_effort=kwargs["reasoning_effort"],
                cost=0.25,
            )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = run_repair_loop_preview_batch(
                PLAN_PATH,
                repo_root=REPO_ROOT,
                output_dir=output_dir,
                trials_dir=output_dir / "trials",
                mini_swe_agent_source_dir=REPO_ROOT,
                config_file=CONFIG_PATH,
                agent_env={},
                max_rows=3,
                parallelism=2,
                runner=fake_runner,
            )
            rows = load_repair_loops(output_dir / "repair-loop-results.json")

        self.assertEqual(len(calls), 3)
        self.assertEqual(max_active, 2)
        self.assertEqual(report["parallelism"], 2)
        self.assertEqual(report["completed_rows"], 3)
        self.assertEqual([row.model_config for row in rows[:2]], [
            "openrouter/anthropic/claude-fable-5[low]",
            "openrouter/anthropic/claude-sonnet-5[low]",
        ])

    def test_preview_batch_skips_existing_rows_and_stops_before_budget_overrun(self) -> None:
        def fail_if_called(**kwargs):
            raise AssertionError("runner should not be called after hard-stop guard")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            first_item = build_repair_loop_preview_schedule(
                PLAN_PATH,
                repo_root=REPO_ROOT,
                output_dir=output_dir,
            )[0]
            first_item.output_path.parent.mkdir(parents=True)
            first_item.output_path.write_text(
                dump_repair_loops(
                    [
                        _result(
                            model=first_item.model_name,
                            task_id=first_item.task_id,
                            reasoning_effort=first_item.reasoning_effort,
                            cost=249.0,
                        )
                    ]
                )
            )

            report = run_repair_loop_preview_batch(
                PLAN_PATH,
                repo_root=REPO_ROOT,
                output_dir=output_dir,
                trials_dir=output_dir / "trials",
                mini_swe_agent_source_dir=REPO_ROOT,
                config_file=CONFIG_PATH,
                agent_env={},
                max_rows=2,
                runner=fail_if_called,
            )

        self.assertTrue(report["stopped"])
        self.assertEqual(report["stop_reason"], "global_hard_stop")
        self.assertEqual(report["completed_rows"], 1)
        self.assertEqual(report["skipped_existing_rows"], 1)
        self.assertEqual(report["remaining_rows"], 1)


def _result(
    *,
    model: str,
    task_id: str,
    reasoning_effort: str | None,
    cost: float,
) -> RepairLoopResult:
    return RepairLoopResult(
        model=model,
        task_id=task_id,
        category="artifact",
        size="small",
        loop=0,
        passed=True,
        stop_reason="passed",
        verifier_submissions=1,
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=0,
        cache_write_tokens=0,
        turns=1,
        agent_steps=1,
        inference_gateway="openrouter" if model.startswith("openrouter/") else None,
        requested_model=model,
        reasoning_effort=reasoning_effort,
        gateway_reported_cost_usd=cost,
        status="scored",
    )


if __name__ == "__main__":
    unittest.main()

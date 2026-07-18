from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

import kaggle_benchmarks as kbench
from kaggle_benchmarks.actors.llms import LLMChat, LLMResponse
from minisweagent.environments.local import LocalEnvironment

from shallowswe.kaggle_repair_loop import (
    _preflight_secure_environment,
    run_kaggle_repair_loop,
)
from shallowswe.kaggle_runtime import HiddenVerifierResult
from shallowswe.repair_loop_protocol import VerifierOutcome
from shallowswe.results import ModelPrice


class _ScriptedLLM(LLMChat):
    def __init__(self, commands: list[str]) -> None:
        super().__init__(name="scripted", support_temperature=True)
        self.commands = list(commands)

    def invoke(self, messages, system, tools=None, **kwargs):
        del messages, system, tools, kwargs
        command = self.commands.pop(0)
        return LLMResponse(
            content="Working.",
            tool_calls=[
                {
                    "id": f"call-{len(self.commands)}",
                    "function": {
                        "name": "bash",
                        "arguments": json.dumps({"command": command}),
                    },
                }
            ],
            meta={"input_tokens": 8, "output_tokens": 4},
        )


class KaggleRepairLoopTests(unittest.TestCase):
    def test_secure_environment_preflight_fails_closed(self) -> None:
        class FailedEnvironment:
            def execute(self, action):
                del action
                return {"returncode": 1, "output": "sandbox unavailable"}

        with self.assertRaisesRegex(RuntimeError, "sandbox preflight failed"):
            _preflight_secure_environment(FailedEnvironment())  # type: ignore[arg-type]

    def test_run_uses_canonical_task_and_sanitized_continuation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _write_task(root / "task")
            workspace = root / "workspace"
            artifacts = root / "artifacts"
            config = root / "config.yaml"
            config.write_text("agent:\n  step_limit: 10\n")
            llm = _ScriptedLLM(
                [
                    "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
                    "printf repaired > fixed.txt",
                    "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
                ]
            )
            verifier_calls = 0

            def verifier_runner() -> HiddenVerifierResult:
                nonlocal verifier_calls
                verifier_calls += 1
                if (workspace / "fixed.txt").exists():
                    return HiddenVerifierResult(VerifierOutcome("passed"), "secret pass")
                return HiddenVerifierResult(
                    VerifierOutcome("output_mismatch"),
                    "secret expected value must never reach the model",
                )

            with kbench.chats.new("repair-loop") as chat:
                row = run_kaggle_repair_loop(
                    llm=llm,
                    task_path=task,
                    verifier_dir=task / "tests",
                    workspace_dir=workspace,
                    artifacts_dir=artifacts,
                    run_id="test-run",
                    model_name="test/model",
                    config_file=config,
                    max_verifier_submissions=3,
                    agent_step_cap=10,
                    seed=7,
                    model_config_id="mc_test",
                    model_config_canonical_json={"requested_model": "test/model"},
                    agent_policy_id="ap_test",
                    agent_policy_canonical_json={"runner": "kaggle"},
                    context_limit=1000,
                    cache_policy="disabled",
                    experiment_id="test-experiment",
                    run_spec_id="test-spec",
                    run_unit_id="test-unit",
                    run_metadata={"phase": "test"},
                    price_sheet_version="test-prices",
                    routine_review_version="review-v1",
                    canonical_price=ModelPrice(1.0, None, 1.0),
                    environment_factory=lambda path, timeout: LocalEnvironment(
                        cwd=str(path), timeout=timeout
                    ),
                    verifier_runner=verifier_runner,
                )

            self.assertTrue(row.passed)
            self.assertEqual(row.stop_reason, "passed")
            self.assertEqual(row.verifier_submissions, 2)
            self.assertEqual(row.turns, 3)
            self.assertEqual(row.runner, "kaggle-benchmarks-repair-loop")
            self.assertEqual(row.inference_gateway, "kaggle")
            self.assertEqual(row.seed, 7)
            self.assertEqual(row.model_config_id, "mc_test")
            self.assertEqual(row.agent_policy_id, "ap_test")
            self.assertEqual(row.verifier_submission_cap, 3)
            self.assertEqual(row.agent_step_cap, 10)
            self.assertEqual(row.experiment_id, "test-experiment")
            self.assertEqual(row.run_spec_id, "test-spec")
            self.assertEqual(row.run_unit_id, "test-unit")
            self.assertEqual(row.run_metadata, {"phase": "test"})
            self.assertEqual(row.censoring_status, "observed")
            self.assertIsNotNone(row.canonical_list_price_equivalent_spend_usd)
            self.assertIsNotNone(row.event_checkpoints)
            assert row.event_checkpoints is not None
            self.assertEqual(
                [checkpoint["event_type"] for checkpoint in row.event_checkpoints],
                ["agent_submission", "verifier_result", "agent_submission", "verifier_result"],
            )
            self.assertEqual(row.event_checkpoints[-1]["result_class"], "passed")
            self.assertTrue(
                all(
                    checkpoint["cumulative_canonical_spend_usd"] is not None
                    for checkpoint in row.event_checkpoints
                )
            )
            self.assertEqual(verifier_calls, 2)
            self.assertTrue((artifacts / "mini-swe-agent.trajectory.json").is_file())
            self.assertTrue((artifacts / "verifier-diagnostics.jsonl").is_file())
            user_messages = [
                message.text for message in chat.messages if message.sender.role == "user"
            ]
            self.assertIn("Verification failed: output mismatch.", user_messages)
            self.assertFalse(any("secret expected value" in message for message in user_messages))

    def test_submission_cap_is_right_censored(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _write_task(root / "task")
            config = root / "config.yaml"
            config.write_text("agent:\n  step_limit: 10\n")
            llm = _ScriptedLLM(["echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"])

            with kbench.chats.new("submission-cap"):
                row = run_kaggle_repair_loop(
                    llm=llm,
                    task_path=task,
                    verifier_dir=task / "tests",
                    workspace_dir=root / "workspace",
                    artifacts_dir=root / "artifacts",
                    run_id="submission-cap",
                    model_name="test/model",
                    config_file=config,
                    max_verifier_submissions=1,
                    environment_factory=lambda path, timeout: LocalEnvironment(
                        cwd=str(path), timeout=timeout
                    ),
                    verifier_runner=lambda: HiddenVerifierResult(
                        VerifierOutcome("output_mismatch"), "hidden"
                    ),
                )

            self.assertEqual(row.stop_reason, "verifier_submission_cap")
            self.assertEqual(row.censoring_status, "right_censored")


def _write_task(task: Path) -> Path:
    environment = task / "environment"
    tests = task / "tests"
    environment.mkdir(parents=True)
    tests.mkdir()
    (environment / "Dockerfile").write_text(
        """\
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY . /app
"""
    )
    (environment / "base.txt").write_text("base\n")
    (task / "instruction.md").write_text("Create fixed.txt.\n")
    (task / "task.toml").write_text(
        """\
schema_version = "1.2"

[task]
name = "shallowswe/runtime-test"

[metadata]
category = "artifact"
size = "small"

[verifier]
timeout_sec = 120.0
"""
    )
    (tests / "test.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    return task


if __name__ == "__main__":
    unittest.main()

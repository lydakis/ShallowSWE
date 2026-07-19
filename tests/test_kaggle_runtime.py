from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest

import kaggle_benchmarks as kbench
from kaggle_benchmarks.actors.llms import LLMChat, LLMResponse
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent.exceptions import FormatError

from shallowswe.kaggle_runtime import (
    KaggleBenchmarksModel,
    build_chroot_command,
    is_kaggle_task_creation_placeholder,
    model_kwargs_for_proxy,
    model_proxy_api,
)
from shallowswe.pier_repair_loop import _raw_usage_totals_from_trajectory
from shallowswe.results import ModelPrice


class _ScriptedLLM(LLMChat):
    def __init__(
        self,
        commands: list[str],
        *,
        resolved_model: str | None = "test/model-snapshot",
    ) -> None:
        super().__init__(name="scripted", support_temperature=True)
        self.commands = list(commands)
        self.seen_roles: list[list[str]] = []
        self.resolved_model = resolved_model

    def invoke(self, messages, system, tools=None, **kwargs):
        del system, kwargs
        self.seen_roles.append([message.sender.role for message in messages])
        self.assert_tools = tools
        command = self.commands.pop(0)
        metadata = {
            "input_tokens": 10,
            "output_tokens": 5,
            "input_tokens_cost_nanodollars": 1_000_000,
            "output_tokens_cost_nanodollars": 2_000_000,
        }
        if self.resolved_model is not None:
            metadata["resolved_model"] = self.resolved_model
        return LLMResponse(
            content=f"Running {command}",
            tool_calls=[
                {
                    "id": f"call-{len(self.seen_roles)}",
                    "function": {
                        "name": "bash",
                        "arguments": json.dumps({"command": command}),
                    },
                }
            ],
            meta=metadata,
        )


class _ProviderResponseLLM(_ScriptedLLM):
    def __init__(self) -> None:
        super().__init__(["true"], resolved_model=None)
        self.client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_kwargs: SimpleNamespace(model="provider/model-snapshot")
                )
            )
        )

    def invoke(self, *args: object, **kwargs: object) -> LLMResponse:
        self.client.chat.completions.create()
        return super().invoke(*args, **kwargs)


class _EmptyThenCommandLLM(_ScriptedLLM):
    def __init__(self) -> None:
        super().__init__(["true"])
        self._empty_pending = True

    def invoke(self, messages, system, tools=None, **kwargs):
        if self._empty_pending:
            self._empty_pending = False
            self.seen_roles.append([message.sender.role for message in messages])
            return LLMResponse(content="", tool_calls=None, meta={})
        return super().invoke(messages, system, tools=tools, **kwargs)


class KaggleRuntimeTests(unittest.TestCase):
    def test_only_exact_kaggle_creation_placeholder_is_skipped(self) -> None:
        self.assertTrue(
            is_kaggle_task_creation_placeholder(
                "google/gemini-3-flash-preview",
                expected_model="gpt-5.6-sol",
            )
        )
        self.assertFalse(
            is_kaggle_task_creation_placeholder(
                "gemini-3.5-flash",
                expected_model="gpt-5.6-sol",
            )
        )
        self.assertFalse(
            is_kaggle_task_creation_placeholder(
                "gpt-5.6-luna",
                expected_model="gpt-5.6-sol",
            )
        )

    def test_runner_uses_runner_supplied_model_after_creation_placeholder_guard(self) -> None:
        source = Path("kaggle/shallowswe_runner.py").read_text()

        guard = source.index("if is_kaggle_task_creation_placeholder(")
        resolution = source.index("model_entry = resolve_model_config(")
        runner_model_use = source.index("llm=llm,")

        self.assertLess(guard, resolution)
        self.assertLess(guard, runner_model_use)
        self.assertNotIn("load_model(", source)

    def test_runner_redirects_verbose_evaluation_output_to_an_artifact(self) -> None:
        source = Path("kaggle/shallowswe_runner.py").read_text()

        redirect = source.index("with redirect_stdout(evaluation_log), redirect_stderr")
        evaluation = source.index("SHALLOWSWE_RUNS = shallowswe_repair_loop.evaluate(")
        completion = source.index('"event": "shallowswe_evaluation_complete"')

        self.assertLess(redirect, evaluation)
        self.assertLess(evaluation, completion)

    def test_captures_resolved_model_from_raw_provider_response(self) -> None:
        llm = _ProviderResponseLLM()
        model = KaggleBenchmarksModel(llm=llm, model_name="requested/model-alias")

        model.query([{"role": "user", "content": "inspect the repository"}])

        self.assertEqual(model.resolved_model, "provider/model-snapshot")

    def test_empty_provider_turn_is_hidden_before_format_error_retry(self) -> None:
        llm = _EmptyThenCommandLLM()
        model = KaggleBenchmarksModel(llm=llm, model_name="test/model")
        messages = [{"role": "user", "content": "inspect"}]

        with kbench.chats.new("empty-response-retry") as chat:
            with self.assertRaises(FormatError):
                model.query(messages)
            messages.append(
                {
                    "role": "user",
                    "content": "Tool call error: issue a bash tool call.",
                }
            )
            second = model.query(messages)

        self.assertTrue(second["tool_calls"])
        self.assertEqual(llm.seen_roles[1], ["user", "user"])
        blank = [message for message in chat.messages if not message.content]
        self.assertEqual(len(blank), 1)
        self.assertFalse(blank[0].is_visible_to_llm)

    def test_google_models_use_genai_model_proxy_api(self) -> None:
        self.assertEqual(model_proxy_api("google/gemini-3.5-flash"), "genai")
        self.assertEqual(
            model_proxy_api("gemini-3.5-flash", upstream_provider="google"),
            "genai",
        )
        self.assertEqual(model_proxy_api("openai/gpt-5.5-2026-04-23"), "openai")
        self.assertEqual(
            model_kwargs_for_proxy(
                "google/gemini-3.5-flash", {"max_tokens": 256, "top_p": 0.9}
            ),
            {"max_output_tokens": 256, "top_p": 0.9},
        )
        self.assertEqual(
            model_kwargs_for_proxy(
                "gemini-3.5-flash",
                {"max_tokens": 256},
                proxy_api="genai",
            ),
            {"max_output_tokens": 256},
        )

    def test_model_adapter_uses_explicit_proxy_api_for_unqualified_kaggle_name(self) -> None:
        model = KaggleBenchmarksModel(
            llm=_ScriptedLLM([]),
            model_name="gemini-3.5-flash",
            proxy_api="genai",
            model_kwargs={"max_tokens": 256},
        )

        self.assertEqual(model.config.model_kwargs, {"max_output_tokens": 256})

    def test_model_adapter_runs_and_resumes_the_same_mini_swe_agent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            trajectory = root / "trajectory.json"
            llm = _ScriptedLLM(
                [
                    "printf first > first.txt",
                    "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
                    "printf repaired > repaired.txt",
                    "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
                ]
            )
            model = KaggleBenchmarksModel(
                llm=llm,
                model_name="test/model",
                canonical_price=ModelPrice(100.0, None, 200.0),
            )
            environment = LocalEnvironment(cwd=str(root))
            agent = InteractiveAgent(
                model,
                environment,
                system_template="System prompt.",
                instance_template="Task: {{task}}",
                mode="yolo",
                confirm_exit=False,
                step_limit=10,
                cost_limit=1.0,
                output_path=trajectory,
            )

            with kbench.chats.new("repair-loop") as chat:
                first = agent.run("Fix it.")
                second = agent.resume(agent.serialize(), "Verification failed: output mismatch.")

            self.assertEqual(first["exit_status"], "Submitted")
            self.assertEqual(second["exit_status"], "Submitted")
            self.assertEqual((root / "first.txt").read_text(), "first")
            self.assertEqual((root / "repaired.txt").read_text(), "repaired")
            self.assertEqual(len(llm.commands), 0)
            self.assertEqual(model.resolved_model, "test/model-snapshot")
            self.assertTrue(llm.assert_tools)
            visible = [message for message in chat.messages if message.is_visible_to_llm]
            roles = [message.sender.role for message in visible]
            self.assertEqual(roles.count("system"), 1)
            self.assertEqual(roles.count("user"), 2)
            self.assertEqual(roles.count("assistant"), 4)
            self.assertEqual(roles.count("tool"), 4)
            self.assertTrue(
                all(message.tool_calls for message in visible if message.sender.role == "assistant")
            )

            usage = _raw_usage_totals_from_trajectory(trajectory)
            self.assertIsNotNone(usage)
            assert usage is not None
            self.assertEqual(usage["input_tokens"], 40)
            self.assertEqual(usage["output_tokens"], 20)
            self.assertAlmostEqual(usage["gateway_reported_cost_usd"], 0.012)
            self.assertAlmostEqual(agent.cost, 0.008)

    def test_chroot_command_drops_privileges_and_inherits_network_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            rootfs = Path(tmp) / "rootfs"
            (rootfs / "app").mkdir(parents=True)

            command = build_chroot_command(
                rootfs=rootfs,
                command="python -c 'print(1)'",
            )

        rendered = " ".join(command)
        self.assertIn("shallowswe.sandbox_exec", command)
        self.assertIn("chroot", command)
        self.assertIn("--userspec=65534:65534", command)
        self.assertIn(str(rootfs.resolve()), command)
        self.assertIn("PATH=/opt/go/bin:/opt/python/bin:/usr/bin:/bin", command)
        self.assertIn("GOROOT=/opt/go", command)
        self.assertIn("GOTOOLCHAIN=local", command)
        self.assertIn("GOCACHE=/tmp/go-build", command)
        self.assertNotIn("/kaggle/input", rendered)
        self.assertNotIn("/proc", rendered)


if __name__ == "__main__":
    unittest.main()

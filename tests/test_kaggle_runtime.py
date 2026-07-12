from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

import kaggle_benchmarks as kbench
from kaggle_benchmarks.actors.llms import LLMChat, LLMResponse
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.environments.local import LocalEnvironment

from shallowswe.kaggle_runtime import (
    KaggleBenchmarksModel,
    build_chroot_command,
    model_kwargs_for_proxy,
    model_proxy_api,
)
from shallowswe.pier_repair_loop import _raw_usage_totals_from_trajectory


class _ScriptedLLM(LLMChat):
    def __init__(self, commands: list[str]) -> None:
        super().__init__(name="scripted", support_temperature=True)
        self.commands = list(commands)
        self.seen_roles: list[list[str]] = []

    def invoke(self, messages, system, tools=None, **kwargs):
        del system, kwargs
        self.seen_roles.append([message.sender.role for message in messages])
        self.assert_tools = tools
        command = self.commands.pop(0)
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
            meta={
                "input_tokens": 10,
                "output_tokens": 5,
                "input_tokens_cost_nanodollars": 1_000_000,
                "output_tokens_cost_nanodollars": 2_000_000,
            },
        )


class KaggleRuntimeTests(unittest.TestCase):
    def test_google_models_use_genai_model_proxy_api(self) -> None:
        self.assertEqual(model_proxy_api("google/gemini-3.5-flash"), "genai")
        self.assertEqual(model_proxy_api("openai/gpt-5.5-2026-04-23"), "openai")
        self.assertEqual(
            model_kwargs_for_proxy(
                "google/gemini-3.5-flash", {"max_tokens": 256, "top_p": 0.9}
            ),
            {"max_output_tokens": 256, "top_p": 0.9},
        )

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
            model = KaggleBenchmarksModel(llm=llm, model_name="test/model")
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
        self.assertNotIn("/kaggle/input", rendered)
        self.assertNotIn("/proc", rendered)


if __name__ == "__main__":
    unittest.main()

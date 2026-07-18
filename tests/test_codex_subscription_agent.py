from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
import asyncio

from shallowswe.pier_agents.codex_subscription_agent import CodexSubscriptionAgent
from shallowswe.pier_agents.resumable_codex_subscription_agent import (
    ResumableCodexSubscriptionAgent,
    _codex_exec_command,
)


class CodexSubscriptionAgentTests(unittest.TestCase):
    def test_network_allowlist_includes_chatgpt_subscription_domains(self) -> None:
        with TemporaryDirectory() as tmp:
            agent = CodexSubscriptionAgent(
                logs_dir=Path(tmp),
                model_name="openai/gpt-5.5",
            )

        domains = set(agent.network_allowlist().domains)

        self.assertIn("api.openai.com", domains)
        self.assertIn("chatgpt.com", domains)

    def test_resumable_agent_uses_same_subscription_allowlist(self) -> None:
        with TemporaryDirectory() as tmp:
            agent = ResumableCodexSubscriptionAgent(
                logs_dir=Path(tmp),
                model_name="openai/gpt-5.5",
            )
            one_shot_agent = CodexSubscriptionAgent(
                logs_dir=Path(tmp),
                model_name="openai/gpt-5.5",
            )

            self.assertEqual(
                set(agent.network_allowlist().domains),
                set(one_shot_agent.network_allowlist().domains),
            )

    def test_first_submission_starts_a_new_codex_session(self) -> None:
        command = _codex_exec_command(
            model="gpt-5.5",
            instruction="Implement the task.",
            cli_flags="-c model_reasoning_effort=high",
            submission_number=1,
        )

        self.assertIn("codex exec --dangerously-bypass-approvals-and-sandbox", command)
        self.assertNotIn("codex exec resume", command)
        self.assertIn("codex-submission-1.txt", command)

    def test_later_submission_resumes_the_same_codex_session(self) -> None:
        command = _codex_exec_command(
            model="gpt-5.5",
            instruction="Verification failed. Continue working.",
            cli_flags="-c model_reasoning_effort=high",
            submission_number=2,
        )

        self.assertIn("codex exec resume --last", command)
        self.assertIn("Verification failed. Continue working.", command)
        self.assertIn("codex-submission-2.txt", command)

    def test_cleanup_removes_uploaded_auth_before_container_teardown(self) -> None:
        calls = []

        class RecordingAgent(ResumableCodexSubscriptionAgent):
            async def exec_as_root(self, environment, *, command, **kwargs):
                del environment, kwargs
                calls.append(command)

        with TemporaryDirectory() as tmp:
            agent = RecordingAgent(logs_dir=Path(tmp), model_name="openai/gpt-5.5")
            agent._runtime_initialized = True
            asyncio.run(agent.cleanup_runtime(SimpleNamespace()))

        self.assertEqual(len(calls), 1)
        self.assertIn("/tmp/codex-secrets", calls[0])
        self.assertIn("/tmp/codex-home", calls[0])
        self.assertFalse(agent._runtime_initialized)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from shallowswe.pier_agents.codex_subscription_agent import CodexSubscriptionAgent


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


if __name__ == "__main__":
    unittest.main()

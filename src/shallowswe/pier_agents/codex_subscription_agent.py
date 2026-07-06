from __future__ import annotations

from pier.agents.installed.codex import Codex
from pier.models.agent.network import NetworkAllowlist


class CodexSubscriptionAgent(Codex):
    """Pier Codex agent variant for local ChatGPT subscription auth."""

    @staticmethod
    def name() -> str:
        return "shallowswe-codex-subscription"

    def network_allowlist(self) -> NetworkAllowlist:
        base = super().network_allowlist()
        return NetworkAllowlist(
            domains=[
                *base.domains,
                "chatgpt.com",
            ]
        )

from __future__ import annotations

import unittest

from shallowswe.identity import agent_policy_id, canonical_json, model_config_id


class IdentityTests(unittest.TestCase):
    def test_canonical_json_is_order_independent(self) -> None:
        self.assertEqual(
            canonical_json({"b": 2, "a": {"d": 4, "c": 3}}),
            canonical_json({"a": {"c": 3, "d": 4}, "b": 2}),
        )

    def test_model_config_id_changes_with_route(self) -> None:
        base = {
            "requested_model": "openai/gpt-test",
            "resolved_model": "openai/gpt-test-2026-07-11",
            "provider_route": "kaggle/openai",
            "reasoning_effort": "high",
        }
        self.assertEqual(model_config_id(base), model_config_id(dict(reversed(list(base.items())))))
        self.assertNotEqual(
            model_config_id(base),
            model_config_id({**base, "provider_route": "openrouter/openai"}),
        )

    def test_agent_policy_id_includes_model_identity(self) -> None:
        policy = {"runner": "kaggle", "prompt_hash": "sha256:prompt"}
        self.assertNotEqual(
            agent_policy_id(policy, model_config_id="mc_one"),
            agent_policy_id(policy, model_config_id="mc_two"),
        )


if __name__ == "__main__":
    unittest.main()

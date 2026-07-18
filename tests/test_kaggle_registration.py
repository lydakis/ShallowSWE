from __future__ import annotations

import unittest

from shallowswe.kaggle_registration import is_development_registration_probe


class KaggleRegistrationTests(unittest.TestCase):
    def test_accepts_only_observed_gemini_probe_for_development_shadow(self) -> None:
        self.assertTrue(
            is_development_registration_probe(
                registration_requested=True,
                plan_class="development_shadow",
                launch_model="openai/gpt-5.4-mini-2026-03-17",
                observed_model="google/gemini-3-flash-preview",
            )
        )
        self.assertFalse(
            is_development_registration_probe(
                registration_requested=True,
                plan_class="official_pilot",
                launch_model="openai/gpt-5.4-mini-2026-03-17",
                observed_model="google/gemini-3-flash-preview",
            )
        )
        self.assertFalse(
            is_development_registration_probe(
                registration_requested=True,
                plan_class="development_shadow",
                launch_model="openai/gpt-5.4-mini-2026-03-17",
                observed_model="openai/gpt-5.4-2026-03-05",
            )
        )

    def test_does_not_mask_a_gemini_launch(self) -> None:
        self.assertFalse(
            is_development_registration_probe(
                registration_requested=True,
                plan_class="development_shadow",
                launch_model="google/gemini-3-flash-preview",
                observed_model="google/gemini-3-flash-preview",
            )
        )

    def test_does_not_mask_a_misrouted_evaluation_without_explicit_sentinel(self) -> None:
        self.assertFalse(
            is_development_registration_probe(
                registration_requested=False,
                plan_class="development_shadow",
                launch_model="openai/gpt-5.4-mini-2026-03-17",
                observed_model="google/gemini-3-flash-preview",
            )
        )


if __name__ == "__main__":
    unittest.main()

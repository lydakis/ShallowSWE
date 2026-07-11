from __future__ import annotations

import asyncio
import unittest

from shallowswe.repair_loop_protocol import (
    AgentSubmission,
    RepairLoopPolicy,
    VerifierOutcome,
    execute_repair_loop,
)


class _FakeBackend:
    def __init__(
        self,
        submissions: list[AgentSubmission],
        verifier_outcomes: list[VerifierOutcome],
    ) -> None:
        self.submissions = list(submissions)
        self.verifier_outcomes = list(verifier_outcomes)
        self.instructions: list[str] = []

    async def submit(self, instruction: str) -> AgentSubmission:
        self.instructions.append(instruction)
        return self.submissions.pop(0)

    async def verify(self) -> VerifierOutcome:
        return self.verifier_outcomes.pop(0)


class RepairLoopProtocolTests(unittest.TestCase):
    def test_failed_submission_continues_same_loop_with_sanitized_feedback(self) -> None:
        backend = _FakeBackend(
            submissions=[AgentSubmission("Submitted"), AgentSubmission("Submitted")],
            verifier_outcomes=[
                VerifierOutcome("output_mismatch"),
                VerifierOutcome("passed"),
            ],
        )

        result = asyncio.run(
            execute_repair_loop(
                backend,
                initial_instruction="Fix the task.",
                policy=RepairLoopPolicy(max_verifier_submissions=3),
            )
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.stop_reason, "passed")
        self.assertEqual(result.verifier_submissions, 2)
        self.assertEqual(result.agent_submissions, 2)
        self.assertEqual(
            backend.instructions,
            ["Fix the task.", "Verification failed: output mismatch."],
        )

    def test_submission_cap_is_a_scored_failure(self) -> None:
        backend = _FakeBackend(
            submissions=[AgentSubmission("Submitted"), AgentSubmission("Submitted")],
            verifier_outcomes=[
                VerifierOutcome("generic_failure"),
                VerifierOutcome("runtime_error"),
            ],
        )

        result = asyncio.run(
            execute_repair_loop(
                backend,
                initial_instruction="Fix the task.",
                policy=RepairLoopPolicy(max_verifier_submissions=2),
            )
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.stop_reason, "verifier_submission_cap")
        self.assertEqual(result.status, "scored")
        self.assertIsNone(result.exclusion_reason)
        self.assertEqual(result.verifier_submissions, 2)

    def test_verifier_infrastructure_error_is_excluded(self) -> None:
        backend = _FakeBackend(
            submissions=[AgentSubmission("Submitted")],
            verifier_outcomes=[VerifierOutcome("verifier_infra_error")],
        )

        result = asyncio.run(
            execute_repair_loop(
                backend,
                initial_instruction="Fix the task.",
                policy=RepairLoopPolicy(max_verifier_submissions=3),
            )
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.stop_reason, "verifier_infra_error")
        self.assertEqual(result.status, "excluded")
        self.assertEqual(result.exclusion_reason, "verifier_infrastructure_error")

    def test_agent_exit_classification_is_backend_independent(self) -> None:
        cases = [
            (AgentSubmission("TimeExceeded"), "wall_time_cap", "excluded"),
            (AgentSubmission("LimitsExceeded"), "agent_step_cap", "scored"),
            (AgentSubmission("LimitsExceeded", dollar_cap_hit=True), "dollar_cap", "scored"),
            (AgentSubmission(None), "agent_exit_unknown", "scored"),
        ]
        for submission, expected_stop_reason, expected_status in cases:
            with self.subTest(expected_stop_reason=expected_stop_reason):
                backend = _FakeBackend([submission], [])
                result = asyncio.run(
                    execute_repair_loop(
                        backend,
                        initial_instruction="Fix the task.",
                        policy=RepairLoopPolicy(max_verifier_submissions=3),
                    )
                )
                self.assertEqual(result.stop_reason, expected_stop_reason)
                self.assertEqual(result.status, expected_status)
                self.assertEqual(result.verifier_submissions, 0)

    def test_invalid_policy_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_verifier_submissions"):
            RepairLoopPolicy(max_verifier_submissions=0)
        with self.assertRaisesRegex(ValueError, "wall_time_cap_seconds"):
            RepairLoopPolicy(max_verifier_submissions=1, wall_time_cap_seconds=0)


if __name__ == "__main__":
    unittest.main()

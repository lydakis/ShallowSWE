from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Protocol
import time


VerifierClass = Literal[
    "passed",
    "generic_failure",
    "runtime_error",
    "missing_required_artifact",
    "output_mismatch",
    "verifier_infra_error",
]

VERIFIER_FEEDBACK: dict[VerifierClass, str] = {
    "passed": "Verification passed.",
    "generic_failure": "Verification failed. Continue working.",
    "runtime_error": "Verification failed: runtime error.",
    "missing_required_artifact": "Verification failed: missing required artifact.",
    "output_mismatch": "Verification failed: output mismatch.",
    "verifier_infra_error": "Verification failed.",
}


@dataclass(frozen=True)
class RepairLoopPolicy:
    max_verifier_submissions: int
    wall_time_cap_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.max_verifier_submissions < 1:
            raise ValueError("max_verifier_submissions must be positive")
        if self.wall_time_cap_seconds is not None and self.wall_time_cap_seconds <= 0:
            raise ValueError("wall_time_cap_seconds must be positive")


@dataclass(frozen=True)
class AgentSubmission:
    exit_status: str | None
    dollar_cap_hit: bool = False


@dataclass(frozen=True)
class VerifierOutcome:
    result_class: VerifierClass

    def __post_init__(self) -> None:
        if self.result_class not in VERIFIER_FEEDBACK:
            raise ValueError(f"unsupported verifier result class: {self.result_class}")

    @property
    def passed(self) -> bool:
        return self.result_class == "passed"


@dataclass(frozen=True)
class RepairLoopExecution:
    passed: bool
    stop_reason: str
    verifier_submissions: int
    agent_submissions: int
    status: str
    exclusion_reason: str | None


class RepairLoopBackend(Protocol):
    async def submit(self, instruction: str) -> AgentSubmission: ...

    async def verify(self) -> VerifierOutcome: ...


async def execute_repair_loop(
    backend: RepairLoopBackend,
    *,
    initial_instruction: str,
    policy: RepairLoopPolicy,
    monotonic: Callable[[], float] = time.monotonic,
    monotonic_started_at: float | None = None,
) -> RepairLoopExecution:
    started_at = monotonic() if monotonic_started_at is None else monotonic_started_at
    instruction = initial_instruction
    verifier_submissions = 0
    agent_submissions = 0

    for _ in range(policy.max_verifier_submissions):
        if _wall_time_expired(started_at, policy.wall_time_cap_seconds, monotonic):
            return _execution(
                stop_reason="wall_time_cap",
                verifier_submissions=verifier_submissions,
                agent_submissions=agent_submissions,
                status="excluded",
                exclusion_reason="infra_wall_time_guard",
            )

        submission = await backend.submit(instruction)
        agent_submissions += 1
        if submission.exit_status != "Submitted":
            status, exclusion_reason = _agent_status(submission)
            return _execution(
                stop_reason=_agent_stop_reason(submission),
                verifier_submissions=verifier_submissions,
                agent_submissions=agent_submissions,
                status=status,
                exclusion_reason=exclusion_reason,
            )

        verifier = await backend.verify()
        verifier_submissions += 1
        if verifier.passed:
            return _execution(
                passed=True,
                stop_reason="passed",
                verifier_submissions=verifier_submissions,
                agent_submissions=agent_submissions,
            )
        if verifier.result_class == "verifier_infra_error":
            return _execution(
                stop_reason="verifier_infra_error",
                verifier_submissions=verifier_submissions,
                agent_submissions=agent_submissions,
                status="excluded",
                exclusion_reason="verifier_infrastructure_error",
            )
        if submission.dollar_cap_hit:
            return _execution(
                stop_reason="dollar_cap",
                verifier_submissions=verifier_submissions,
                agent_submissions=agent_submissions,
            )
        instruction = VERIFIER_FEEDBACK[verifier.result_class]

    return _execution(
        stop_reason="verifier_submission_cap",
        verifier_submissions=verifier_submissions,
        agent_submissions=agent_submissions,
    )


def _execution(
    *,
    stop_reason: str,
    verifier_submissions: int,
    agent_submissions: int,
    passed: bool = False,
    status: str = "scored",
    exclusion_reason: str | None = None,
) -> RepairLoopExecution:
    return RepairLoopExecution(
        passed=passed,
        stop_reason=stop_reason,
        verifier_submissions=verifier_submissions,
        agent_submissions=agent_submissions,
        status=status,
        exclusion_reason=exclusion_reason,
    )


def _agent_stop_reason(submission: AgentSubmission) -> str:
    if submission.exit_status == "TimeExceeded":
        return "wall_time_cap"
    if submission.exit_status == "LimitsExceeded":
        return "dollar_cap" if submission.dollar_cap_hit else "agent_step_cap"
    if submission.exit_status:
        return f"agent_exit_{submission.exit_status.lower()}"
    return "agent_exit_unknown"


def _agent_status(submission: AgentSubmission) -> tuple[str, str | None]:
    if submission.exit_status == "TimeExceeded":
        return ("excluded", "infra_wall_time_guard")
    return ("scored", None)


def _wall_time_expired(
    started_at: float,
    wall_time_cap_seconds: int | None,
    monotonic: Callable[[], float],
) -> bool:
    if wall_time_cap_seconds is None:
        return False
    return monotonic() - started_at >= wall_time_cap_seconds

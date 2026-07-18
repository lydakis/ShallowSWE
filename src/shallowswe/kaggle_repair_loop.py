from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import asyncio
import hashlib
import importlib.metadata
import json
import time
import tomllib
import traceback

from .kaggle_bundle import materialize_task_environment, tree_sha256
from .kaggle_runtime import (
    HiddenVerifierResult,
    KaggleBenchmarksModel,
    KaggleSandboxEnvironment,
    run_hidden_verifier,
)
from .repair_loop_protocol import (
    AgentSubmission,
    RepairLoopPolicy,
    VerifierOutcome,
    execute_repair_loop,
)
from .mini_swe_config import (
    effective_scaffold_prompt_hash,
    load_effective_mini_swe_config,
)
from .results import (
    CAP_HIT_STOP_REASONS,
    EXCLUDED_STATUS,
    ModelPrice,
    RepairLoopResult,
    usage_cost_usd,
)
from .task_metadata import load_task
from .trajectory_usage import raw_usage_totals_from_trajectory


KAGGLE_RUNNER = "kaggle-benchmarks-repair-loop"
MINI_SWE_AGENT_COMMIT = "8c3cfaee0ddb37c8325426990ff179c96690a1cf"

EnvironmentFactory = Callable[[Path, int], Any]
VerifierRunner = Callable[[], HiddenVerifierResult]


def run_kaggle_repair_loop(
    *,
    llm: Any,
    task_path: Path,
    verifier_dir: Path,
    workspace_dir: Path,
    artifacts_dir: Path,
    run_id: str,
    model_name: str,
    config_file: Path,
    max_verifier_submissions: int = 3,
    agent_step_cap: int | None = None,
    dollar_cap_usd: float | None = None,
    wall_time_cap_seconds: int | None = None,
    reasoning_effort: str | None = None,
    temperature: float = 0.0,
    seed: int = 0,
    task_suite_version: str = "shallowswe-v0.1-candidate",
    repo_commit_sha: str | None = None,
    model_config_id: str | None = None,
    model_config_canonical_json: dict[str, Any] | None = None,
    agent_policy_id: str | None = None,
    agent_policy_canonical_json: dict[str, Any] | None = None,
    provider_route: str = "kaggle_model_proxy",
    context_limit: int | None = None,
    cache_policy: str | None = None,
    price_sheet_version: str | None = None,
    routine_review_version: str | None = None,
    trajectory_id: str | None = None,
    experiment_id: str | None = None,
    run_spec_id: str | None = None,
    run_unit_id: str | None = None,
    run_metadata: dict[str, Any] | None = None,
    result_accounting: dict[str, Any] | None = None,
    canonical_price: ModelPrice | None = None,
    proxy_api: str | None = None,
    environment_factory: EnvironmentFactory | None = None,
    verifier_runner: VerifierRunner | None = None,
) -> RepairLoopResult:
    policy = RepairLoopPolicy(
        max_verifier_submissions=max_verifier_submissions,
        wall_time_cap_seconds=wall_time_cap_seconds,
    )
    if dollar_cap_usd is not None and dollar_cap_usd <= 0:
        raise ValueError("dollar_cap_usd must be positive")
    if agent_step_cap is not None and agent_step_cap <= 0:
        raise ValueError("agent_step_cap must be positive")
    accounting = dict(result_accounting or {})
    required_price_sheet = accounting.get("required_price_sheet_version")
    if required_price_sheet is not None and price_sheet_version != required_price_sheet:
        raise ValueError(
            "runtime price sheet does not match frozen accounting policy: "
            f"{price_sheet_version!r} != {required_price_sheet!r}"
        )

    task_contract = {
        "task_version": _task_contract_hash(task_path, verifier_dir),
        "verifier_hash": tree_sha256(verifier_dir),
        "environment_image_digest": tree_sha256(task_path / "environment"),
    }
    expected_contract = {
        "task_version": accounting.get("expected_task_version"),
        "verifier_hash": accounting.get("expected_verifier_hash"),
        "environment_image_digest": accounting.get(
            "expected_environment_image_digest"
        ),
    }
    if any(value is not None for value in expected_contract.values()):
        if any(not isinstance(value, str) or not value for value in expected_contract.values()):
            raise ValueError("runtime requires a complete frozen task contract")
        if expected_contract != task_contract:
            raise ValueError(
                "runtime task contract does not match frozen accounting policy: "
                f"{task_contract!r} != {expected_contract!r}"
            )

    shallow_task = load_task(task_path)
    started_at = datetime.now(timezone.utc)
    monotonic_started_at = time.monotonic()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = artifacts_dir / "mini-swe-agent.trajectory.json"
    diagnostics_path = artifacts_dir / "verifier-diagnostics.jsonl"
    checkpoints_path = artifacts_dir / "repair-loop-checkpoints.jsonl"
    exception_path = artifacts_dir / "runner-exception.txt"
    materialize_task_environment(task_path, workspace_dir)

    config = load_effective_mini_swe_config(config_file)
    agent_config = dict(config.get("agent") or {})
    model_config = dict(config.get("model") or {})
    model_kwargs = dict(model_config.get("model_kwargs") or {})
    model_kwargs.pop("drop_params", None)
    model_config["model_kwargs"] = model_kwargs
    model_config.update(
        {
            "model_name": model_name,
            "seed": seed,
            "temperature": temperature,
            "reasoning": reasoning_effort,
        }
    )
    model = KaggleBenchmarksModel(
        llm=llm,
        canonical_price=canonical_price,
        proxy_api=proxy_api,
        **model_config,
    )
    command_timeout = int((config.get("environment") or {}).get("timeout") or 30)
    selected_environment_factory = environment_factory or _secure_environment
    environment = selected_environment_factory(workspace_dir, command_timeout)
    secure_environment = environment if environment_factory is None else None

    from minisweagent.agents import get_agent

    agent_config.update(
        {
            "mode": "yolo",
            "confirm_exit": False,
            "output_path": trajectory_path,
            **({"step_limit": agent_step_cap} if agent_step_cap is not None else {}),
            **(
                {"cost_limit": dollar_cap_usd}
                if dollar_cap_usd is not None
                else {}
            ),
            **(
                {"wall_time_limit_seconds": wall_time_cap_seconds}
                if wall_time_cap_seconds is not None
                else {}
            ),
        }
    )
    agent = get_agent(model, environment, agent_config, default_type="interactive")

    logs_dir = artifacts_dir / "verifier-logs"
    selected_verifier_runner = verifier_runner or (
        lambda: run_hidden_verifier(
            workspace=(
                secure_environment.task_workspace
                if secure_environment is not None
                else workspace_dir
            ),
            verifier_dir=verifier_dir,
            logs_dir=logs_dir,
            timeout_seconds=_verifier_timeout_seconds(task_path),
            rootfs=(secure_environment.rootfs if secure_environment is not None else None),
        )
    )
    backend = _KaggleRepairLoopBackend(
        agent=agent,
        verifier_runner=selected_verifier_runner,
        diagnostics_path=diagnostics_path,
        checkpoints_path=checkpoints_path,
        trajectory_path=trajectory_path,
        canonical_price=canonical_price,
        dollar_cap_usd=dollar_cap_usd,
    )

    execution = None
    try:
        if environment_factory is None:
            _preflight_secure_environment(environment)
        execution = _run_async(
            execute_repair_loop(
                backend,
                initial_instruction=(task_path / "instruction.md").read_text(),
                policy=policy,
                monotonic_started_at=monotonic_started_at,
            )
        )
        passed = execution.passed
        stop_reason = execution.stop_reason
        status = execution.status
        exclusion_reason = execution.exclusion_reason
    except Exception:
        exception_path.write_text(traceback.format_exc())
        passed = False
        stop_reason = "runner_exception"
        status = EXCLUDED_STATUS
        exclusion_reason = "runner_infrastructure_error"
    finally:
        if secure_environment is not None:
            secure_environment.export_workspace()

    finished_at = datetime.now(timezone.utc)
    usage = raw_usage_totals_from_trajectory(trajectory_path) or {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "gateway_reported_cost_usd": None,
    }
    canonical_spend = _canonical_usage_cost(usage, canonical_price)
    reference_budget = accounting.get("reference_task_budget_usd")
    replacement_cost = accounting.get("reference_anchor_replacement_cost_usd")
    reference_charge = (
        canonical_spend
        if passed
        else float(reference_budget)
        if reference_budget is not None
        else None
    )
    escalation_charge = (
        canonical_spend
        + (0.0 if passed else float(replacement_cost))
        if canonical_spend is not None and (passed or replacement_cost is not None)
        else None
    )
    return RepairLoopResult(
        model=model_name,
        task_id=shallow_task.task_id,
        category=shallow_task.category,
        size=shallow_task.size,
        loop=seed,
        passed=passed,
        stop_reason=stop_reason,
        verifier_submissions=backend.verifier_submissions,
        input_tokens=int(usage["input_tokens"]),
        output_tokens=int(usage["output_tokens"]),
        cache_read_tokens=int(usage["cache_read_tokens"]),
        cache_write_tokens=int(usage["cache_write_tokens"]),
        turns=int(getattr(agent, "n_calls", 0)),
        agent_steps=int(getattr(agent, "n_calls", 0)),
        peak_context_tokens=None,
        reasoning_tokens=int(usage["reasoning_tokens"]),
        temperature=temperature,
        sampling_config={
            "model_name": model_name,
            "reasoning_effort": reasoning_effort,
            "temperature": temperature,
            "seed": seed,
            "model_kwargs": model_kwargs,
        },
        gateway_reported_cost_usd=usage["gateway_reported_cost_usd"],
        agent="shallowswe-resumable-mini-swe-agent",
        agent_version=f"mini-swe-agent@{MINI_SWE_AGENT_COMMIT}",
        runner=KAGGLE_RUNNER,
        runner_version=_package_version("kaggle-benchmarks"),
        scaffold_prompt_hash=effective_scaffold_prompt_hash(config),
        token_source="kaggle-benchmarks-message-usage",
        inference_gateway="kaggle",
        requested_model=model_name,
        resolved_model=model.resolved_model,
        reasoning_effort=reasoning_effort,
        task_version=task_contract["task_version"],
        task_suite_version=task_suite_version,
        verifier_hash=task_contract["verifier_hash"],
        environment_image_digest=task_contract["environment_image_digest"],
        repo_commit_sha=repo_commit_sha,
        price_sheet_version=price_sheet_version,
        seed=seed,
        run_id=run_id,
        trajectory_id=trajectory_id,
        experiment_id=experiment_id,
        run_spec_id=run_spec_id,
        run_unit_id=run_unit_id,
        run_metadata=run_metadata,
        task_visibility="kaggle-chroot-seccomp-hidden-verifier",
        transcript_hash=_file_hash(trajectory_path),
        model_config_id=model_config_id,
        model_config_canonical_json=model_config_canonical_json,
        agent_policy_id=agent_policy_id,
        agent_policy_canonical_json=agent_policy_canonical_json,
        provider_route=provider_route,
        context_limit=context_limit,
        max_output_tokens=(
            int(model_kwargs["max_tokens"]) if model_kwargs.get("max_tokens") is not None else None
        ),
        cache_policy=cache_policy,
        reference_task_budget_usd=_accounting_float(
            accounting,
            "reference_task_budget_usd",
        ),
        reference_budget_version=_accounting_str(accounting, "reference_budget_version"),
        reference_budget_band=_accounting_str(accounting, "reference_budget_band"),
        reference_budget_coverage_target=_accounting_float(
            accounting,
            "reference_budget_coverage_target",
        ),
        reference_budget_proposal_attempts=_accounting_int(
            accounting,
            "reference_budget_proposal_attempts",
        ),
        reference_budget_development_check_attempts=_accounting_int(
            accounting,
            "reference_budget_development_check_attempts",
        ),
        reference_budget_band_bumps=_accounting_int(
            accounting,
            "reference_budget_band_bumps",
        ),
        primary_anchor_model_config_id=_accounting_str(
            accounting,
            "primary_anchor_model_config_id",
        ),
        anchor_price_sheet_version=_accounting_str(
            accounting,
            "anchor_price_sheet_version",
        ),
        reference_anchor_replacement_cost_usd=_accounting_float(
            accounting,
            "reference_anchor_replacement_cost_usd",
        ),
        anchor_confirmation_attempts=_accounting_int(
            accounting,
            "anchor_confirmation_attempts",
        ),
        anchor_confirmation_successes=_accounting_int(
            accounting,
            "anchor_confirmation_successes",
        ),
        actual_model_spend_usd=usage["gateway_reported_cost_usd"],
        canonical_list_price_equivalent_spend_usd=canonical_spend,
        reference_budget_charged_spend_usd=reference_charge,
        realized_charged_spend_usd=canonical_spend,
        escalation_charged_spend_usd=escalation_charge,
        failure_charge_applied_usd=(
            float(reference_budget)
            if not passed and reference_budget is not None
            else 0.0
            if passed and reference_budget is not None
            else None
        ),
        budget_overrun_usd=(
            max(0.0, canonical_spend - float(reference_budget))
            if canonical_spend is not None and reference_budget is not None
            else None
        ),
        verifier_submission_cap=max_verifier_submissions,
        agent_step_cap=int(agent_config.get("step_limit") or 0) or None,
        cap_disclosure="undisclosed",
        pressure_band=_accounting_str(accounting, "pressure_band"),
        routine_review_version=routine_review_version,
        censoring_status=("right_censored" if stop_reason in CAP_HIT_STOP_REASONS else "observed"),
        event_checkpoints=backend.event_checkpoints,
        status=status,
        exclusion_reason=exclusion_reason,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
    )


def _accounting_float(accounting: dict[str, Any], field: str) -> float | None:
    value = accounting.get(field)
    return float(value) if value is not None else None


def _accounting_int(accounting: dict[str, Any], field: str) -> int | None:
    value = accounting.get(field)
    return int(value) if value is not None else None


def _accounting_str(accounting: dict[str, Any], field: str) -> str | None:
    value = accounting.get(field)
    return str(value) if value is not None else None


class _KaggleRepairLoopBackend:
    def __init__(
        self,
        *,
        agent: Any,
        verifier_runner: VerifierRunner,
        diagnostics_path: Path,
        checkpoints_path: Path,
        trajectory_path: Path,
        canonical_price: ModelPrice | None,
        dollar_cap_usd: float | None,
    ) -> None:
        self.agent = agent
        self.verifier_runner = verifier_runner
        self.diagnostics_path = diagnostics_path
        self.checkpoints_path = checkpoints_path
        self.trajectory_path = trajectory_path
        self.canonical_price = canonical_price
        self.dollar_cap_usd = dollar_cap_usd
        self.verifier_submissions = 0
        self.agent_submissions = 0
        self.event_checkpoints: list[dict[str, Any]] = []
        self._started = False

    async def submit(self, instruction: str) -> AgentSubmission:
        if self._started:
            result = self.agent.resume(self.agent.serialize(), instruction)
        else:
            result = self.agent.run(instruction)
            self._started = True
        self.agent_submissions += 1
        cost = float(getattr(self.agent, "cost", 0.0) or 0.0)
        self._record_checkpoint(event_type="agent_submission")
        return AgentSubmission(
            exit_status=result.get("exit_status"),
            dollar_cap_hit=(
                self.dollar_cap_usd is not None and cost >= self.dollar_cap_usd
            ),
        )

    async def verify(self) -> VerifierOutcome:
        result = self.verifier_runner()
        self.verifier_submissions += 1
        self._record_checkpoint(
            event_type="verifier_result",
            result_class=result.outcome.result_class,
        )
        with self.diagnostics_path.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "submission": self.verifier_submissions,
                        "result_class": result.outcome.result_class,
                        "diagnostics": result.diagnostics,
                    }
                )
                + "\n"
            )
        return result.outcome

    def _record_checkpoint(
        self,
        *,
        event_type: str,
        result_class: str | None = None,
    ) -> None:
        usage = raw_usage_totals_from_trajectory(self.trajectory_path) or {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "gateway_reported_cost_usd": None,
        }
        checkpoint = {
            "event_index": len(self.event_checkpoints) + 1,
            "event_type": event_type,
            "agent_submission": self.agent_submissions,
            "verifier_submission": self.verifier_submissions,
            "result_class": result_class,
            "cumulative_input_tokens": int(usage["input_tokens"]),
            "cumulative_output_tokens": int(usage["output_tokens"]),
            "cumulative_cache_read_tokens": int(usage["cache_read_tokens"]),
            "cumulative_cache_write_tokens": int(usage["cache_write_tokens"]),
            "cumulative_reasoning_tokens": int(usage["reasoning_tokens"]),
            "cumulative_agent_steps": int(getattr(self.agent, "n_calls", 0)),
            "cumulative_gateway_reported_cost_usd": usage[
                "gateway_reported_cost_usd"
            ],
            "cumulative_canonical_spend_usd": _canonical_usage_cost(
                usage,
                self.canonical_price,
            ),
        }
        self.event_checkpoints.append(checkpoint)
        with self.checkpoints_path.open("a") as handle:
            handle.write(json.dumps(checkpoint) + "\n")


def _canonical_usage_cost(
    usage: dict[str, Any],
    price: ModelPrice | None,
) -> float | None:
    if price is None:
        return None
    return usage_cost_usd(
        input_tokens=int(usage["input_tokens"]),
        output_tokens=int(usage["output_tokens"]),
        cache_read_tokens=int(usage["cache_read_tokens"]),
        cache_write_tokens=int(usage["cache_write_tokens"]),
        price=price,
    )


def dump_kaggle_result(row: RepairLoopResult) -> str:
    return json.dumps([asdict(row)], indent=2) + "\n"


def _secure_environment(workspace: Path, command_timeout: int) -> KaggleSandboxEnvironment:
    return KaggleSandboxEnvironment(workspace=str(workspace), timeout=command_timeout)


def _preflight_secure_environment(environment: KaggleSandboxEnvironment) -> None:
    output = environment.execute(
        {
            "command": (
                "command -v python >/dev/null && "
                "python -c 'import sys; assert sys.version_info[:2] == (3, 12)' && "
                "! python -c 'import socket; socket.socket()' >/dev/null 2>&1 && "
                "test ! -e /kaggle/input && printf SHALLOWSWE_SANDBOX_OK"
            )
        }
    )
    if output.get("returncode") != 0 or "SHALLOWSWE_SANDBOX_OK" not in str(
        output.get("output", "")
    ):
        raise RuntimeError(f"Kaggle sandbox preflight failed: {output}")


def _verifier_timeout_seconds(task_path: Path) -> int:
    with (task_path / "task.toml").open("rb") as handle:
        raw = tomllib.load(handle)
    verifier = raw.get("verifier") if isinstance(raw.get("verifier"), dict) else {}
    return int(float(verifier.get("timeout_sec") or 120))


def _task_contract_hash(task_path: Path, verifier_dir: Path) -> str:
    hasher = hashlib.sha256()
    for value in (
        tree_sha256(task_path / "environment"),
        _file_hash(task_path / "instruction.md"),
        _file_hash(task_path / "task.toml"),
        tree_sha256(verifier_dir),
    ):
        hasher.update((value or "missing").encode())
        hasher.update(b"\0")
    return f"{task_path.name}@sha256:{hasher.hexdigest()}"


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _run_async(coroutine: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()

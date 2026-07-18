from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import asyncio
import hashlib
import json
import subprocess
import time
import traceback

from pier.models.agent.context import AgentContext
from pier.models.trial.config import AgentConfig, EnvironmentConfig, TaskConfig, TrialConfig
from pier.models.trial.result import ExceptionInfo, TimingInfo, TrialResult
from pier.models.verifier.result import VerifierResult
from pier.trial.trial import Trial

from .repair_loop_protocol import (
    AgentSubmission,
    RepairLoopPolicy,
    VERIFIER_FEEDBACK,
    VerifierOutcome,
    execute_repair_loop,
)
from .mini_swe_config import effective_scaffold_prompt_hash, load_effective_mini_swe_config
from .results import (
    CAP_HIT_STOP_REASONS,
    EXCLUDED_STATUS,
    ModelPrice,
    RepairLoopResult,
    usage_cost_usd,
)
from .task_metadata import load_task
from .trajectory_usage import raw_usage_totals_from_trajectory as _raw_usage_totals_from_trajectory


RESUMABLE_MINI_SWE_AGENT_IMPORT_PATH = (
    "shallowswe.pier_agents.resumable_mini_swe_agent:ResumableMiniSweAgent"
)
RESUMABLE_CODEX_SUBSCRIPTION_AGENT_IMPORT_PATH = (
    "shallowswe.pier_agents.resumable_codex_subscription_agent:"
    "ResumableCodexSubscriptionAgent"
)
DEFAULT_REPAIR_FEEDBACK = VERIFIER_FEEDBACK["generic_failure"]


def run_pier_repair_loop(
    *,
    task_path: Path,
    trials_dir: Path,
    trial_name: str,
    model_name: str,
    mini_swe_agent_source_dir: Path,
    config_file: Path,
    agent_env: dict[str, str],
    max_verifier_submissions: int = 3,
    dollar_cap_usd: float | None = None,
    wall_time_cap_seconds: int | None = None,
    environment_type: str = "docker",
    reasoning_effort: str | None = None,
    seed: int = 0,
    agent_import_path: str = RESUMABLE_MINI_SWE_AGENT_IMPORT_PATH,
    agent_kwargs: dict[str, Any] | None = None,
    trajectory_filename: str = "mini-swe-agent.trajectory.json",
    inference_gateway: str | None = None,
    upstream_provider: str | None = None,
    provider_route: str | None = None,
    trajectory_id: str | None = None,
    experiment_id: str | None = None,
    run_spec_id: str | None = None,
    run_unit_id: str | None = None,
    run_metadata: dict[str, Any] | None = None,
    canonical_price: ModelPrice | None = None,
    price_sheet_version: str | None = None,
    price_sheet_date: str | None = None,
    model_config_id: str | None = None,
    model_config_canonical_json: dict[str, Any] | None = None,
    agent_policy_id: str | None = None,
    agent_policy_canonical_json: dict[str, Any] | None = None,
) -> RepairLoopResult:
    if max_verifier_submissions < 1:
        raise ValueError("max_verifier_submissions must be positive")
    if dollar_cap_usd is not None and dollar_cap_usd <= 0:
        raise ValueError("dollar_cap_usd must be positive")
    if wall_time_cap_seconds is not None and wall_time_cap_seconds <= 0:
        raise ValueError("wall_time_cap_seconds must be positive")
    return asyncio.run(
        _run_pier_repair_loop(
            task_path=task_path,
            trials_dir=trials_dir,
            trial_name=trial_name,
            model_name=model_name,
            mini_swe_agent_source_dir=mini_swe_agent_source_dir,
            config_file=config_file,
            agent_env=agent_env,
            max_verifier_submissions=max_verifier_submissions,
            dollar_cap_usd=dollar_cap_usd,
            wall_time_cap_seconds=wall_time_cap_seconds,
            environment_type=environment_type,
            reasoning_effort=reasoning_effort,
            seed=seed,
            agent_import_path=agent_import_path,
            agent_kwargs=agent_kwargs,
            trajectory_filename=trajectory_filename,
            inference_gateway=inference_gateway,
            upstream_provider=upstream_provider,
            provider_route=provider_route,
            trajectory_id=trajectory_id,
            experiment_id=experiment_id,
            run_spec_id=run_spec_id,
            run_unit_id=run_unit_id,
            run_metadata=run_metadata,
            canonical_price=canonical_price,
            price_sheet_version=price_sheet_version,
            price_sheet_date=price_sheet_date,
            model_config_id=model_config_id,
            model_config_canonical_json=model_config_canonical_json,
            agent_policy_id=agent_policy_id,
            agent_policy_canonical_json=agent_policy_canonical_json,
        )
    )


def dump_repair_loop_rows(rows: list[RepairLoopResult]) -> str:
    return json.dumps([asdict(row) for row in rows], indent=2) + "\n"


def load_env_file(path: Path, keys: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in keys:
            values[key] = value.strip().strip("'\"")
    return values


async def _run_pier_repair_loop(
    *,
    task_path: Path,
    trials_dir: Path,
    trial_name: str,
    model_name: str,
    mini_swe_agent_source_dir: Path,
    config_file: Path,
    agent_env: dict[str, str],
    max_verifier_submissions: int,
    dollar_cap_usd: float | None,
    wall_time_cap_seconds: int | None,
    environment_type: str,
    reasoning_effort: str | None,
    seed: int,
    agent_import_path: str,
    agent_kwargs: dict[str, Any] | None,
    trajectory_filename: str,
    inference_gateway: str | None,
    upstream_provider: str | None,
    provider_route: str | None,
    trajectory_id: str | None,
    experiment_id: str | None,
    run_spec_id: str | None,
    run_unit_id: str | None,
    run_metadata: dict[str, Any] | None,
    canonical_price: ModelPrice | None,
    price_sheet_version: str | None,
    price_sheet_date: str | None,
    model_config_id: str | None,
    model_config_canonical_json: dict[str, Any] | None,
    agent_policy_id: str | None,
    agent_policy_canonical_json: dict[str, Any] | None,
) -> RepairLoopResult:
    shallow_task = load_task(task_path)
    sampling_config = _sampling_config_from_file(
        config_file=config_file,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
    )
    started_at = datetime.now(timezone.utc)
    monotonic_started_at = time.monotonic()
    config = TrialConfig(
        task=TaskConfig(path=task_path),
        trial_name=trial_name,
        trials_dir=trials_dir,
        agent=AgentConfig(
            import_path=agent_import_path,
            model_name=model_name,
            kwargs=(
                dict(agent_kwargs)
                if agent_kwargs is not None
                else {
                    "mini_swe_agent_source_dir": str(mini_swe_agent_source_dir),
                    "config_file": str(config_file),
                    **(
                        {"cost_limit": dollar_cap_usd}
                        if dollar_cap_usd is not None
                        else {}
                    ),
                    **(
                        {"reasoning_effort": reasoning_effort}
                        if reasoning_effort is not None
                        else {}
                    ),
                }
            ),
            env=agent_env,
        ),
        environment=EnvironmentConfig(type=environment_type, delete=True),
    )
    trial = await Trial.create(config)
    _initialize_trial_result(trial, started_at=started_at)

    contexts: list[AgentContext] = []
    passed = False
    stop_reason = "verifier_submission_cap"
    status = "scored"
    exclusion_reason = None
    trajectory_path = trial._trial_paths.agent_dir / trajectory_filename
    backend: _PierRepairLoopBackend | None = None

    try:
        await trial._setup_environment()
        await trial._environment.run_healthcheck()
        trial._environment.default_user = trial._task.config.agent.user
        await trial._setup_agent()
        trial._result.agent_info = trial._agent.to_agent_info()

        backend = _PierRepairLoopBackend(
            trial=trial,
            contexts=contexts,
            trajectory_path=trajectory_path,
            dollar_cap_usd=dollar_cap_usd,
            canonical_price=canonical_price,
        )
        execution = await execute_repair_loop(
            backend,
            initial_instruction=trial._task.instruction,
            policy=RepairLoopPolicy(
                max_verifier_submissions=max_verifier_submissions,
                wall_time_cap_seconds=wall_time_cap_seconds,
            ),
            monotonic_started_at=monotonic_started_at,
        )
        passed = execution.passed
        stop_reason = execution.stop_reason
        status = execution.status
        exclusion_reason = execution.exclusion_reason
    except Exception as exc:
        trial.result.exception_info = ExceptionInfo.from_exception(exc)
        trial._trial_paths.exception_message_path.write_text(traceback.format_exc())
        stop_reason, status, exclusion_reason = _classify_runner_exception()
    finally:
        try:
            cleanup_runtime = getattr(trial._agent, "cleanup_runtime", None)
            if cleanup_runtime is not None:
                try:
                    await cleanup_runtime(trial._environment)
                except Exception as exc:
                    trial.result.exception_info = ExceptionInfo.from_exception(exc)
                    trial._trial_paths.exception_message_path.write_text(traceback.format_exc())
                    stop_reason, status, exclusion_reason = _classify_runner_exception()
            await trial._cleanup_and_finalize()
        finally:
            trial._close_logger_handler()

    finished_at = datetime.now(timezone.utc)
    final_context = contexts[-1] if contexts else AgentContext()
    usage = _final_usage_totals(final_context, trajectory_path)
    transcript_hash = _file_sha256(trajectory_path)
    agent_steps = int(usage.get("agent_steps") or final_context.n_agent_steps or 0)
    canonical_spend = _canonical_usage_cost(usage, canonical_price)
    return RepairLoopResult(
        model=model_name,
        task_id=shallow_task.task_id,
        category=shallow_task.category,
        size=shallow_task.size,
        loop=seed,
        passed=passed,
        stop_reason=stop_reason,
        verifier_submissions=backend.verifier_submissions if backend is not None else 0,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cache_read_tokens=usage["cache_read_tokens"],
        cache_write_tokens=usage["cache_write_tokens"],
        turns=agent_steps,
        agent_steps=agent_steps,
        peak_context_tokens=final_context.peak_context_tokens,
        reasoning_tokens=usage["reasoning_tokens"],
        temperature=_temperature_from_sampling_config(sampling_config),
        sampling_config=sampling_config,
        gateway_reported_cost_usd=usage["gateway_reported_cost_usd"],
        agent=trial._agent.name(),
        agent_version=trial._agent.version(),
        runner="pier-repair-loop",
        runner_version=_git_head_sha(Path(__file__).resolve().parents[2]),
        scaffold_prompt_hash=_scaffold_prompt_hash(
            agent_import_path=agent_import_path,
            config_file=config_file,
            mini_swe_agent_source_dir=mini_swe_agent_source_dir,
        ),
        token_source=(
            "atif_final_metrics"
            if _atif_usage_totals_from_trajectory(trajectory_path) is not None
            else "raw_provider_usage"
        ),
        inference_gateway=inference_gateway or _gateway_from_model_name(model_name),
        upstream_provider=upstream_provider,
        requested_model=model_name,
        resolved_model=_resolved_model_from_trajectory(trajectory_path),
        reasoning_effort=reasoning_effort,
        task_version=f"{shallow_task.task_id}@local",
        task_suite_version="shallowswe-v0.1-candidate",
        verifier_hash=_tree_sha256(task_path / "tests"),
        environment_image_digest=_tree_sha256(task_path / "environment"),
        repo_commit_sha=_git_head_sha(task_path),
        price_sheet_version=price_sheet_version,
        price_sheet_date=price_sheet_date,
        seed=seed,
        run_id=trial_name,
        trajectory_id=trajectory_id,
        experiment_id=experiment_id,
        run_spec_id=run_spec_id,
        run_unit_id=run_unit_id,
        run_metadata=run_metadata,
        task_visibility="local-hidden-verifier",
        transcript_hash=transcript_hash,
        verifier_submission_cap=max_verifier_submissions,
        agent_step_cap=_agent_step_cap_for_backend(
            agent_import_path=agent_import_path,
            config_file=config_file,
        ),
        censoring_status=(
            "right_censored" if stop_reason in CAP_HIT_STOP_REASONS else "observed"
        ),
        event_checkpoints=backend.event_checkpoints if backend is not None else [],
        model_config_id=model_config_id,
        model_config_canonical_json=model_config_canonical_json,
        agent_policy_id=agent_policy_id,
        agent_policy_canonical_json=agent_policy_canonical_json,
        provider_route=provider_route,
        actual_model_spend_usd=usage["gateway_reported_cost_usd"],
        canonical_list_price_equivalent_spend_usd=canonical_spend,
        status=status,
        exclusion_reason=exclusion_reason,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
    )


class _PierRepairLoopBackend:
    def __init__(
        self,
        *,
        trial: Trial,
        contexts: list[AgentContext],
        trajectory_path: Path,
        dollar_cap_usd: float | None,
        canonical_price: ModelPrice | None,
    ) -> None:
        self.trial = trial
        self.contexts = contexts
        self.trajectory_path = trajectory_path
        self.dollar_cap_usd = dollar_cap_usd
        self.canonical_price = canonical_price
        self.verifier_submissions = 0
        self.agent_submissions = 0
        self.event_checkpoints: list[dict[str, Any]] = []

    async def submit(self, instruction: str) -> AgentSubmission:
        context = AgentContext()
        self.contexts.append(context)
        await _hide_verifier_artifacts(self.trial)
        await _execute_agent_submission(
            trial=self.trial,
            instruction=instruction,
            context=context,
        )
        self.agent_submissions += 1
        self._record_checkpoint(event_type="agent_submission")
        return AgentSubmission(
            exit_status=_agent_exit_status(self.trajectory_path),
            dollar_cap_hit=_dollar_cap_hit(
                context=context,
                dollar_cap_usd=self.dollar_cap_usd,
                trajectory_path=self.trajectory_path,
            ),
        )

    async def verify(self) -> VerifierOutcome:
        verifier_result = await _verify_submission(self.trial)
        self.verifier_submissions += 1
        outcome = VerifierOutcome(
            "passed" if _verifier_passed(verifier_result) else "generic_failure"
        )
        self._record_checkpoint(
            event_type="verifier_result",
            result_class=outcome.result_class,
        )
        return outcome

    def _record_checkpoint(
        self,
        *,
        event_type: str,
        result_class: str | None = None,
    ) -> None:
        latest_context = self.contexts[-1] if self.contexts else AgentContext()
        usage = _cumulative_usage_totals(latest_context, self.trajectory_path)
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
            "cumulative_agent_steps": int(
                usage.get("agent_steps") or latest_context.n_agent_steps or 0
            ),
            "cumulative_gateway_reported_cost_usd": usage[
                "gateway_reported_cost_usd"
            ],
            "cumulative_canonical_spend_usd": _canonical_usage_cost(
                usage,
                self.canonical_price,
            ),
        }
        self.event_checkpoints.append(checkpoint)


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
        peak_context_tokens=(
            int(usage["peak_context_tokens"])
            if usage.get("peak_context_tokens") is not None
            else None
        ),
        price=price,
    )


def _initialize_trial_result(trial: Trial, *, started_at: datetime) -> None:
    trial._trial_paths.trial_dir.mkdir(parents=True, exist_ok=True)
    trial._trial_paths.config_path.write_text(trial.config.model_dump_json(indent=4))
    trial._result = TrialResult(
        trial_name=trial.config.trial_name,
        task_name=trial._task.name,
        task_id=trial.config.task.get_task_id(),
        started_at=started_at,
        config=trial.config,
        task_checksum=trial._task.checksum,
        trial_uri=trial._trial_paths.trial_dir.expanduser().resolve().as_uri(),
        agent_info=trial._agent.to_agent_info(),
        source=trial.config.task.source,
    )


async def _execute_agent_submission(
    *,
    trial: Trial,
    instruction: str,
    context: AgentContext,
) -> None:
    trial._are_agent_logs_downloaded = False
    trial.result.agent_execution = TimingInfo(started_at=datetime.now(timezone.utc))
    try:
        trial._environment.default_user = trial._task.config.agent.user
        await trial._execution.run_agent(instruction=instruction, context=context)
        await trial._maybe_download_logs(
            source_dir=trial._environment.env_paths.agent_dir.as_posix(),
            target_dir=trial._trial_paths.agent_dir,
        )
        trial._maybe_populate_agent_context(context)
        trial.result.agent_result = context
        await trial._run_pre_artifacts_script()
        trial._are_artifacts_collected = False
        await trial._maybe_upload_agent_logs()
        await trial._collect_artifacts()
    finally:
        trial.result.agent_execution.finished_at = datetime.now(timezone.utc)
        trial._environment.default_user = None


async def _hide_verifier_artifacts(trial: Trial) -> None:
    environment = trial._environment
    env_paths = environment.env_paths
    paths = [env_paths.verifier_dir, env_paths.tests_dir]
    # verifier_dir can be a bind mount, so empty it instead of removing the root.
    result = await environment.empty_dirs(paths, chmod=False)
    if result is not None and result.return_code != 0:
        output = result.stderr or result.stdout or "no output"
        raise RuntimeError(
            "Failed to hide verifier artifacts "
            f"{', '.join(str(path) for path in paths)}: {output}"
        )


async def _verify_submission(trial: Trial) -> VerifierResult:
    env_paths = trial._environment.env_paths
    await trial._environment.reset_dirs(
        remove_dirs=[env_paths.verifier_dir, env_paths.tests_dir],
        create_dirs=[env_paths.verifier_dir, env_paths.tests_dir],
        chmod_dirs=[env_paths.verifier_dir],
    )
    trial._environment.default_user = trial._task.config.verifier.user
    try:
        return await trial._verify_once(step_cfg=None)
    finally:
        try:
            await _hide_verifier_artifacts(trial)
        finally:
            trial._environment.default_user = None


def _verifier_passed(verifier_result: VerifierResult) -> bool:
    rewards = verifier_result.rewards or {}
    return float(rewards.get("reward", 0.0)) >= 1.0


def _agent_exit_status(trajectory_path: Path) -> str | None:
    if not trajectory_path.exists():
        return None
    try:
        trajectory = json.loads(trajectory_path.read_text())
    except json.JSONDecodeError:
        return None
    if trajectory.get("schema_version", "").startswith("ATIF-"):
        return "Submitted"
    exit_status = trajectory.get("info", {}).get("exit_status")
    return str(exit_status) if exit_status else None


def _mini_swe_exit_status(trial: Trial) -> str | None:
    return _agent_exit_status(
        trial._trial_paths.agent_dir / "mini-swe-agent.trajectory.json"
    )


def _stop_reason_for_agent_exit(exit_status: str | None) -> str:
    if exit_status == "LimitsExceeded":
        return "agent_step_cap"
    if exit_status == "TimeExceeded":
        return "wall_time_cap"
    if exit_status:
        return f"agent_exit_{exit_status.lower()}"
    return "agent_exit_unknown"


def _classify_agent_exit(
    *,
    exit_status: str | None,
    context: AgentContext,
    dollar_cap_usd: float | None,
    trajectory_path: Path | None = None,
) -> tuple[str, str, str | None]:
    if exit_status == "TimeExceeded":
        return ("wall_time_cap", EXCLUDED_STATUS, "infra_wall_time_guard")
    if exit_status == "LimitsExceeded" and _dollar_cap_hit(
        context=context,
        dollar_cap_usd=dollar_cap_usd,
        trajectory_path=trajectory_path,
    ):
        return ("dollar_cap", "scored", None)
    return (_stop_reason_for_agent_exit(exit_status), "scored", None)


def _classify_runner_exception() -> tuple[str, str, str]:
    return ("runner_exception", EXCLUDED_STATUS, "runner_infrastructure_error")


def _dollar_cap_hit(
    *,
    context: AgentContext,
    dollar_cap_usd: float | None,
    trajectory_path: Path | None = None,
) -> bool:
    cost_usd = _context_or_trajectory_cost(context, trajectory_path)
    if dollar_cap_usd is None or cost_usd is None:
        return False
    return cost_usd >= dollar_cap_usd


def _context_or_trajectory_cost(
    context: AgentContext,
    trajectory_path: Path | None,
) -> float | None:
    if trajectory_path is not None:
        reported_cost = _reported_cost_from_trajectory(trajectory_path)
        if reported_cost is not None:
            return reported_cost
    if context.cost_usd is not None:
        return context.cost_usd
    if trajectory_path is not None:
        usage = _raw_usage_totals_from_trajectory(trajectory_path)
        if usage:
            return usage["gateway_reported_cost_usd"]
    return None


def _final_usage_totals(context: AgentContext, trajectory_path: Path) -> dict[str, Any]:
    raw_usage = _raw_usage_totals_from_trajectory(trajectory_path)
    atif_usage = _atif_usage_totals_from_trajectory(trajectory_path)
    cost_usd = _context_or_trajectory_cost(context, trajectory_path)
    if raw_usage:
        return {
            **raw_usage,
            "gateway_reported_cost_usd": (
                cost_usd
                if cost_usd is not None
                else raw_usage["gateway_reported_cost_usd"]
            ),
        }
    if atif_usage:
        return atif_usage
    return {
        "input_tokens": context.n_input_tokens or 0,
        "output_tokens": context.n_output_tokens or 0,
        "cache_read_tokens": context.n_cache_tokens or 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "gateway_reported_cost_usd": cost_usd,
        "agent_steps": context.n_agent_steps or 0,
    }


def _cumulative_usage_totals(
    context: AgentContext,
    trajectory_path: Path,
) -> dict[str, Any]:
    usage = _raw_usage_totals_from_trajectory(trajectory_path)
    if usage is not None:
        return {**usage, "agent_steps": context.n_agent_steps or 0}
    atif_usage = _atif_usage_totals_from_trajectory(trajectory_path)
    if atif_usage is not None:
        return atif_usage
    return {
        "input_tokens": context.n_input_tokens or 0,
        "output_tokens": context.n_output_tokens or 0,
        "cache_read_tokens": context.n_cache_tokens or 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "gateway_reported_cost_usd": context.cost_usd,
        "agent_steps": context.n_agent_steps or 0,
    }


def _atif_usage_totals_from_trajectory(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        trajectory = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(trajectory, dict):
        return None
    if not str(trajectory.get("schema_version") or "").startswith("ATIF-"):
        return None
    metrics = trajectory.get("final_metrics")
    if not isinstance(metrics, dict):
        return None
    extra = metrics.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    return {
        "input_tokens": _int_or_zero(metrics.get("total_prompt_tokens")),
        "output_tokens": _int_or_zero(metrics.get("total_completion_tokens")),
        "cache_read_tokens": _int_or_zero(metrics.get("total_cached_tokens")),
        "cache_write_tokens": 0,
        "reasoning_tokens": _int_or_zero(extra.get("reasoning_output_tokens")),
        "gateway_reported_cost_usd": _float_or_none(metrics.get("total_cost_usd")),
        "agent_steps": _int_or_zero(metrics.get("total_steps")),
    }


def _reported_cost_from_trajectory(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        trajectory = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None

    if not isinstance(trajectory, dict):
        return None
    info = trajectory.get("info") or {}
    if not isinstance(info, dict):
        return None
    model_stats = info.get("model_stats") or {}
    if not isinstance(model_stats, dict):
        return None
    for key in ("instance_cost", "total_cost_usd", "cost_usd"):
        cost = _float_or_none(model_stats.get(key))
        if cost is not None:
            return cost
    return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _wall_time_expired(
    *,
    monotonic_started_at: float,
    wall_time_cap_seconds: int | None,
) -> bool:
    if wall_time_cap_seconds is None:
        return False
    return time.monotonic() - monotonic_started_at >= wall_time_cap_seconds


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.is_file():
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        return None
    hasher = hashlib.sha256()
    for item in files:
        hasher.update(item.relative_to(path).as_posix().encode())
        hasher.update(b"\0")
        hasher.update(item.read_bytes())
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"


def _git_head_sha(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _resolved_model_from_trajectory(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        trajectory = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(trajectory, dict):
        return None
    agent = trajectory.get("agent")
    if not isinstance(agent, dict):
        return None
    model_name = agent.get("model_name")
    return str(model_name) if model_name else None


def _scaffold_prompt_hash(
    *,
    agent_import_path: str,
    config_file: Path,
    mini_swe_agent_source_dir: Path,
) -> str | None:
    if agent_import_path != RESUMABLE_MINI_SWE_AGENT_IMPORT_PATH:
        return None
    return effective_scaffold_prompt_hash(
        load_effective_mini_swe_config(
            config_file,
            base_config_file=(
                mini_swe_agent_source_dir
                / "src"
                / "minisweagent"
                / "config"
                / "mini.yaml"
            ),
        )
    )


def _sampling_config_from_file(
    *,
    config_file: Path,
    model_name: str,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    config = _load_config_mapping(config_file)
    model_config = config.get("model") if isinstance(config.get("model"), dict) else {}
    sampling: dict[str, Any] = {
        "config_file": str(config_file),
        "model_name": model_name,
        **dict(model_config),
    }
    if reasoning_effort is not None:
        model_kwargs = sampling.get("model_kwargs")
        if not isinstance(model_kwargs, dict):
            model_kwargs = {}
        sampling["model_kwargs"] = {**model_kwargs, "reasoning_effort": reasoning_effort}
    return sampling


def _load_config_mapping(config_file: Path) -> dict[str, Any]:
    if not config_file.exists():
        return {}
    raw = config_file.read_text()
    if config_file.suffix == ".json":
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    try:
        import yaml  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return {}
    loaded = yaml.safe_load(raw)
    return loaded if isinstance(loaded, dict) else {}


def _temperature_from_sampling_config(sampling_config: dict[str, Any] | None) -> float | None:
    value = (sampling_config or {}).get("temperature")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _step_limit_from_config(config_file: Path) -> int | None:
    config = _load_config_mapping(config_file)
    agent = config.get("agent") if isinstance(config.get("agent"), dict) else {}
    value = agent.get("step_limit")
    return int(value) if value is not None else None


def _agent_step_cap_for_backend(
    *,
    agent_import_path: str,
    config_file: Path,
) -> int | None:
    if agent_import_path != RESUMABLE_MINI_SWE_AGENT_IMPORT_PATH:
        return None
    return _step_limit_from_config(config_file)


def _gateway_from_model_name(model_name: str) -> str | None:
    if "/" not in model_name:
        return None
    return model_name.split("/", 1)[0] or None

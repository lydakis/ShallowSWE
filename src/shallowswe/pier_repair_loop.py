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

from .results import EXCLUDED_STATUS, RepairLoopResult
from .task_metadata import load_task


RESUMABLE_MINI_SWE_AGENT_IMPORT_PATH = (
    "shallowswe.pier_agents.resumable_mini_swe_agent:ResumableMiniSweAgent"
)
DEFAULT_REPAIR_FEEDBACK = "Verification failed. Continue working."


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
            import_path=RESUMABLE_MINI_SWE_AGENT_IMPORT_PATH,
            model_name=model_name,
            kwargs={
                "mini_swe_agent_source_dir": str(mini_swe_agent_source_dir),
                "config_file": str(config_file),
                **({"cost_limit": dollar_cap_usd} if dollar_cap_usd is not None else {}),
                **(
                    {"reasoning_effort": reasoning_effort}
                    if reasoning_effort is not None
                    else {}
                ),
            },
            env=agent_env,
        ),
        environment=EnvironmentConfig(type=environment_type, delete=True),
    )
    trial = await Trial.create(config)
    _initialize_trial_result(trial, started_at=started_at)

    contexts: list[AgentContext] = []
    verifier_submissions = 0
    passed = False
    stop_reason = "verifier_submission_cap"
    status = "scored"
    exclusion_reason = None

    try:
        await trial._setup_environment()
        await trial._environment.run_healthcheck()
        trial._environment.default_user = trial._task.config.agent.user
        await trial._setup_agent()
        trial._result.agent_info = trial._agent.to_agent_info()

        feedback = trial._task.instruction
        for _ in range(max_verifier_submissions):
            if _wall_time_expired(
                monotonic_started_at=monotonic_started_at,
                wall_time_cap_seconds=wall_time_cap_seconds,
            ):
                status = "scored"
                exclusion_reason = None
                stop_reason = "wall_time_cap"
                break
            context = AgentContext()
            contexts.append(context)
            await _hide_verifier_artifacts(trial)
            await _execute_agent_submission(trial=trial, instruction=feedback, context=context)
            exit_status = _mini_swe_exit_status(trial)
            if exit_status != "Submitted":
                stop_reason, status, exclusion_reason = _classify_agent_exit(
                    exit_status=exit_status,
                    context=context,
                    dollar_cap_usd=dollar_cap_usd,
                )
                break
            verifier_result = await _verify_submission(trial)
            verifier_submissions += 1
            if _verifier_passed(verifier_result):
                passed = True
                stop_reason = "passed"
                break
            if _dollar_cap_hit(context=context, dollar_cap_usd=dollar_cap_usd):
                stop_reason = "dollar_cap"
                break
            feedback = DEFAULT_REPAIR_FEEDBACK
    except Exception as exc:
        trial.result.exception_info = ExceptionInfo.from_exception(exc)
        trial._trial_paths.exception_message_path.write_text(traceback.format_exc())
        stop_reason, status, exclusion_reason = _classify_runner_exception()
    finally:
        try:
            await trial._cleanup_and_finalize()
        finally:
            trial._close_logger_handler()

    finished_at = datetime.now(timezone.utc)
    final_context = contexts[-1] if contexts else AgentContext()
    transcript_hash = _file_sha256(trial._trial_paths.agent_dir / "mini-swe-agent.trajectory.json")
    return RepairLoopResult(
        model=model_name,
        task_id=shallow_task.task_id,
        category=shallow_task.category,
        size=shallow_task.size,
        loop=seed,
        passed=passed,
        stop_reason=stop_reason,
        verifier_submissions=verifier_submissions,
        input_tokens=final_context.n_input_tokens or 0,
        output_tokens=final_context.n_output_tokens or 0,
        cache_read_tokens=final_context.n_cache_tokens or 0,
        cache_write_tokens=0,
        turns=final_context.n_agent_steps or 0,
        agent_steps=final_context.n_agent_steps or 0,
        peak_context_tokens=final_context.peak_context_tokens,
        temperature=_temperature_from_sampling_config(sampling_config),
        sampling_config=sampling_config,
        gateway_reported_cost_usd=final_context.cost_usd,
        agent="shallowswe-resumable-mini-swe-agent",
        agent_version=trial._agent.version(),
        runner="pier-private-repair-loop-pilot",
        runner_version=_git_head_sha(Path(__file__).resolve().parents[2]),
        scaffold_prompt_hash=_file_sha256(config_file),
        inference_gateway=_gateway_from_model_name(model_name),
        requested_model=model_name,
        reasoning_effort=reasoning_effort,
        task_version=f"{shallow_task.task_id}@local",
        task_suite_version="shallowswe-v0.1-candidate",
        verifier_hash=_tree_sha256(task_path / "tests"),
        environment_image_digest=_tree_sha256(task_path / "environment"),
        repo_commit_sha=_git_head_sha(task_path),
        seed=seed,
        run_id=trial_name,
        task_visibility="local-hidden-verifier",
        transcript_hash=transcript_hash,
        status=status,
        exclusion_reason=exclusion_reason,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
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


def _mini_swe_exit_status(trial: Trial) -> str | None:
    trajectory_path = trial._trial_paths.agent_dir / "mini-swe-agent.trajectory.json"
    if not trajectory_path.exists():
        return None
    try:
        trajectory = json.loads(trajectory_path.read_text())
    except json.JSONDecodeError:
        return None
    exit_status = trajectory.get("info", {}).get("exit_status")
    return str(exit_status) if exit_status else None


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
) -> tuple[str, str, str | None]:
    if exit_status == "TimeExceeded":
        return ("wall_time_cap", "scored", None)
    if exit_status == "LimitsExceeded" and _dollar_cap_hit(
        context=context,
        dollar_cap_usd=dollar_cap_usd,
    ):
        return ("dollar_cap", "scored", None)
    return (_stop_reason_for_agent_exit(exit_status), "scored", None)


def _classify_runner_exception() -> tuple[str, str, str]:
    return ("runner_exception", EXCLUDED_STATUS, "runner_infrastructure_error")


def _dollar_cap_hit(*, context: AgentContext, dollar_cap_usd: float | None) -> bool:
    if dollar_cap_usd is None or context.cost_usd is None:
        return False
    return context.cost_usd >= dollar_cap_usd


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


def _gateway_from_model_name(model_name: str) -> str | None:
    if "/" not in model_name:
        return None
    return model_name.split("/", 1)[0] or None

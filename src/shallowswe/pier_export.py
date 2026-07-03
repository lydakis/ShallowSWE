from __future__ import annotations

from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
import json

from .results import EXCLUDED_STATUS, SCORED_STATUS, RolloutResult
from .task_metadata import ShallowTask, task_index


def export_pier_job(job_dir: Path, tasks_root: Path) -> list[RolloutResult]:
    tasks = task_index(tasks_root)
    trial_paths = sorted(
        path
        for path in job_dir.glob("*/result.json")
        if path.parent.is_dir() and path.parent.name != ".critiques"
    )

    rows: list[RolloutResult] = []
    rollout_counts: dict[tuple[str, str], int] = {}
    for trial_path in trial_paths:
        trial = json.loads(trial_path.read_text())
        task = _resolve_task(trial, tasks)
        model = _model_name(trial)
        key = (model, task.task_id)
        rollout = rollout_counts.get(key, 0)
        rollout_counts[key] = rollout + 1
        trajectory = _load_json_if_exists(trial_path.parent / "agent/trajectory.json")
        raw_trajectory = _load_json_if_exists(
            trial_path.parent / "agent/mini-swe-agent.trajectory.json"
        )
        token_totals = _token_totals(trial, trajectory, raw_trajectory, trial_path)
        agent_info = trial.get("agent_info") or {}
        if not isinstance(agent_info, dict):
            agent_info = {}
        status, exclusion_reason = _status(trial, trial_path.parent)
        sampling_config = _sampling_config(raw_trajectory)

        rows.append(
            RolloutResult(
                model=model,
                provider=_provider(trial),
                inference_gateway=_provider(trial),
                upstream_provider=_upstream_provider(trial, raw_trajectory),
                requested_model=model,
                resolved_model=_resolved_model(raw_trajectory, trajectory),
                reasoning_effort=_reasoning_effort(sampling_config),
                reasoning_tokens=token_totals["reasoning_tokens"],
                temperature=_temperature(sampling_config),
                sampling_config=sampling_config,
                gateway_reported_cost_usd=token_totals["gateway_reported_cost_usd"],
                task_id=task.task_id,
                category=task.category,
                tier=task.tier,
                rollout=rollout,
                passed=status == SCORED_STATUS and _passed(trial),
                input_tokens=token_totals["input_tokens"],
                output_tokens=token_totals["output_tokens"],
                cache_read_tokens=token_totals["cache_read_tokens"],
                cache_write_tokens=token_totals["cache_write_tokens"],
                turns=_turns(trial),
                peak_context_tokens=_peak_context_tokens(trial),
                agent=_optional_str(agent_info.get("name")),
                agent_version=_optional_str(agent_info.get("version")),
                runner="pier",
                runner_version=_package_version("datacurve-pier"),
                scaffold_prompt_hash=_scaffold_prompt_hash(trajectory, raw_trajectory),
                token_source=token_totals["token_source"],
                status=status,
                exclusion_reason=exclusion_reason,
                started_at=_optional_str(trial.get("started_at")),
                finished_at=_optional_str(trial.get("finished_at")),
            )
        )

    return rows


def _resolve_task(trial: dict[str, Any], tasks: dict[str, ShallowTask]) -> ShallowTask:
    task_name = str(trial.get("task_name") or "")
    if task_name in tasks:
        return tasks[task_name]
    short_name = task_name.split("/", 1)[-1]
    if short_name in tasks:
        return tasks[short_name]

    task_id = trial.get("task_id") or {}
    if isinstance(task_id, dict):
        raw_path = str(task_id.get("path") or "")
        if raw_path:
            path_name = Path(raw_path).name
            if path_name in tasks:
                return tasks[path_name]

    raise ValueError(f"could not resolve ShallowSWE task for Pier trial {task_name!r}")


def _model_name(trial: dict[str, Any]) -> str:
    model = _model_info(trial)
    if model and model.get("name"):
        return str(model["name"])
    agent = trial.get("agent_info") or {}
    if isinstance(agent, dict):
        return str(agent.get("name") or "unknown")
    return "unknown"


def _provider(trial: dict[str, Any]) -> str | None:
    model = _model_info(trial)
    return _optional_str(model.get("provider")) if model else None


def _upstream_provider(
    trial: dict[str, Any],
    raw_trajectory: dict[str, Any] | None,
) -> str | None:
    provider = _provider(trial)
    if provider != "openrouter":
        return provider
    model = _resolved_model(raw_trajectory, None) or _model_name(trial)
    if "/" in model:
        return model.split("/", 1)[0]
    return None


def _model_info(trial: dict[str, Any]) -> dict[str, Any] | None:
    agent = trial.get("agent_info") or {}
    if not isinstance(agent, dict):
        return None
    model = agent.get("model_info")
    return model if isinstance(model, dict) else None


def _passed(trial: dict[str, Any]) -> bool:
    verifier = trial.get("verifier_result") or {}
    if not isinstance(verifier, dict):
        return False
    rewards = verifier.get("rewards") or {}
    if not isinstance(rewards, dict):
        return False
    return _float_or_zero(rewards.get("reward")) >= 1.0


def _status(trial: dict[str, Any], trial_dir: Path) -> tuple[str, str | None]:
    exception_info = trial.get("exception_info")
    if not isinstance(exception_info, dict):
        return SCORED_STATUS, None

    haystack = " ".join(
        part
        for part in (
            _optional_str(exception_info.get("exception_type")),
            _optional_str(exception_info.get("exception_message")),
            _optional_str(exception_info.get("exception_traceback")),
            _read_text_if_exists(trial_dir / "agent/mini-swe-agent.txt"),
            _read_text_if_exists(trial_dir / "trial.log"),
        )
        if part
    ).lower()

    if any(
        marker in haystack
        for marker in (
            "openrouterapierror",
            "openrouterratelimiterror",
            "litellm.authenticationerror",
            "litellm.ratelimiterror",
            "litellm.apierror",
            "provider returned error",
            "requires more credits",
            "rate limit exceeded",
            "http 401",
            "http 402",
            "http 429",
            "user not found",
            "request failed:",
            "connection",
            "network",
        )
    ):
        return EXCLUDED_STATUS, "provider_or_network_error"

    if "verifier" in haystack and "exception" in haystack:
        return EXCLUDED_STATUS, "verifier_infrastructure_error"

    return SCORED_STATUS, None


def _turns(trial: dict[str, Any]) -> int:
    agent_result = trial.get("agent_result") or {}
    if not isinstance(agent_result, dict):
        agent_result = {}
    return _int_or_zero(trial.get("n_agent_steps") or agent_result.get("n_agent_steps"))


def _peak_context_tokens(trial: dict[str, Any]) -> int | None:
    agent_result = trial.get("agent_result") or {}
    if not isinstance(agent_result, dict):
        return None
    value = agent_result.get("peak_context_tokens")
    return _int_or_zero(value) if value is not None else None


def _token_totals(
    trial: dict[str, Any],
    trajectory: dict[str, Any] | None,
    raw_trajectory: dict[str, Any] | None,
    trial_path: Path,
) -> dict[str, Any]:
    final_totals = _atif_final_totals(trajectory)
    raw_totals = _raw_usage_totals(raw_trajectory)

    if final_totals and raw_totals:
        comparable = ("input_tokens", "output_tokens", "cache_read_tokens")
        mismatches = [
            name
            for name in comparable
            if int(final_totals[name]) != int(raw_totals[name])
        ]
        if mismatches:
            details = ", ".join(
                f"{name}: atif={final_totals[name]} raw={raw_totals[name]}"
                for name in mismatches
            )
            raise ValueError(f"token totals mismatch in {trial_path}: {details}")
        return {
            **final_totals,
            "cache_write_tokens": raw_totals["cache_write_tokens"],
            "reasoning_tokens": raw_totals["reasoning_tokens"],
            "gateway_reported_cost_usd": raw_totals["gateway_reported_cost_usd"],
            "token_source": "pier_atif_final_metrics_reconciled",
        }

    if final_totals:
        return final_totals

    if raw_totals:
        return raw_totals

    agent_result = trial.get("agent_result") or {}
    if not isinstance(agent_result, dict):
        agent_result = {}
    return {
        "input_tokens": _int_or_zero(agent_result.get("n_input_tokens")),
        "output_tokens": _int_or_zero(agent_result.get("n_output_tokens")),
        "cache_read_tokens": _int_or_zero(agent_result.get("n_cache_tokens")),
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "gateway_reported_cost_usd": _optional_float(agent_result.get("cost_usd")),
        "token_source": "pier_trial_agent_result",
    }


def _atif_final_totals(trajectory: dict[str, Any] | None) -> dict[str, Any] | None:
    final_metrics = (trajectory or {}).get("final_metrics") or {}
    if isinstance(final_metrics, dict) and final_metrics.get("total_prompt_tokens") is not None:
        return {
            "input_tokens": _int_or_zero(final_metrics.get("total_prompt_tokens")),
            "output_tokens": _int_or_zero(final_metrics.get("total_completion_tokens")),
            "cache_read_tokens": _int_or_zero(final_metrics.get("total_cached_tokens")),
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "gateway_reported_cost_usd": None,
            "token_source": "pier_atif_final_metrics",
        }
    return None


def _raw_usage_totals(raw_trajectory: dict[str, Any] | None) -> dict[str, Any] | None:
    usage_entries: list[dict[str, Any]] = []
    _collect_usage_entries(raw_trajectory, usage_entries)
    if not usage_entries:
        return None

    return {
        "input_tokens": sum(_usage_input_tokens(usage) for usage in usage_entries),
        "output_tokens": sum(_usage_output_tokens(usage) for usage in usage_entries),
        "cache_read_tokens": sum(_usage_cache_read_tokens(usage) for usage in usage_entries),
        "cache_write_tokens": sum(_usage_cache_write_tokens(usage) for usage in usage_entries),
        "reasoning_tokens": sum(_usage_reasoning_tokens(usage) for usage in usage_entries),
        "gateway_reported_cost_usd": _sum_optional_float(
            usage.get("cost") for usage in usage_entries
        ),
        "token_source": "raw_provider_usage_recursive",
    }


def _collect_usage_entries(value: Any, entries: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        usage = value.get("usage")
        if isinstance(usage, dict):
            entries.append(usage)
        for child in value.values():
            _collect_usage_entries(child, entries)
    elif isinstance(value, list):
        for child in value:
            _collect_usage_entries(child, entries)


def _usage_input_tokens(usage: dict[str, Any]) -> int:
    return _first_int(usage, ("input_tokens", "prompt_tokens"))


def _usage_output_tokens(usage: dict[str, Any]) -> int:
    return _first_int(usage, ("output_tokens", "completion_tokens"))


def _usage_cache_read_tokens(usage: dict[str, Any]) -> int:
    details = _dict_child(usage, "input_tokens_details") or _dict_child(
        usage, "prompt_tokens_details"
    )
    if details and details.get("cached_tokens") is not None:
        return _int_or_zero(details.get("cached_tokens"))
    return _first_int(usage, ("cache_read_input_tokens", "cached_input_tokens"))


def _usage_cache_write_tokens(usage: dict[str, Any]) -> int:
    details = _dict_child(usage, "input_tokens_details") or _dict_child(
        usage, "prompt_tokens_details"
    )
    if details:
        for key in ("cache_creation_tokens", "cache_write_tokens"):
            if details.get(key) is not None:
                return _int_or_zero(details.get(key))
    return _first_int(usage, ("cache_creation_input_tokens", "cache_write_input_tokens"))


def _usage_reasoning_tokens(usage: dict[str, Any]) -> int:
    details = _dict_child(usage, "output_tokens_details") or _dict_child(
        usage, "completion_tokens_details"
    )
    if details and details.get("reasoning_tokens") is not None:
        return _int_or_zero(details.get("reasoning_tokens"))
    return _first_int(usage, ("reasoning_tokens",))


def _sum_optional_float(values: Any) -> float | None:
    total = 0.0
    found = False
    for value in values:
        if value is None:
            continue
        total += float(value)
        found = True
    return total if found else None


def _dict_child(value: dict[str, Any], key: str) -> dict[str, Any] | None:
    child = value.get(key)
    return child if isinstance(child, dict) else None


def _first_int(value: dict[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        if value.get(key) is not None:
            return _int_or_zero(value.get(key))
    return 0


def _resolved_model(
    raw_trajectory: dict[str, Any] | None,
    trajectory: dict[str, Any] | None,
) -> str | None:
    models: set[str] = set()
    _collect_usage_models(raw_trajectory, models)
    if len(models) == 1:
        return next(iter(models))
    agent = (trajectory or {}).get("agent") or {}
    if isinstance(agent, dict):
        return _optional_str(agent.get("model_name"))
    return None


def _collect_usage_models(value: Any, models: set[str]) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("usage"), dict) and value.get("model"):
            models.add(str(value["model"]))
        for child in value.values():
            _collect_usage_models(child, models)
    elif isinstance(value, list):
        for child in value:
            _collect_usage_models(child, models)


def _scaffold_prompt_hash(
    trajectory: dict[str, Any] | None,
    raw_trajectory: dict[str, Any] | None,
) -> str | None:
    agent = (trajectory or {}).get("agent") or {}
    extra = agent.get("extra") if isinstance(agent, dict) else None
    config = (raw_trajectory or {}).get("info", {}).get("config", {})
    agent_config = (extra or {}).get("agent_config") or config.get("agent")
    if not isinstance(agent_config, dict):
        return None
    payload = {
        "system_template": agent_config.get("system_template"),
        "instance_template": agent_config.get("instance_template"),
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return sha256(encoded).hexdigest()


def _sampling_config(raw_trajectory: dict[str, Any] | None) -> dict[str, Any] | None:
    config: dict[str, Any] = {}
    model_config = (raw_trajectory or {}).get("info", {}).get("config", {}).get("model")
    if isinstance(model_config, dict):
        for key in ("model_kwargs", "set_cache_control", "cost_tracking"):
            if model_config.get(key) is not None:
                config[key] = model_config[key]

    responses: list[dict[str, Any]] = []
    _collect_usage_responses(raw_trajectory, responses)
    for key in ("temperature", "max_output_tokens", "reasoning"):
        value = _unique_non_none(response.get(key) for response in responses)
        if value is not None:
            config[key] = value

    return config or None


def _collect_usage_responses(value: Any, responses: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("usage"), dict):
            responses.append(value)
        for child in value.values():
            _collect_usage_responses(child, responses)
    elif isinstance(value, list):
        for child in value:
            _collect_usage_responses(child, responses)


def _reasoning_effort(sampling_config: dict[str, Any] | None) -> str | None:
    reasoning = (sampling_config or {}).get("reasoning")
    if isinstance(reasoning, dict):
        return _optional_str(reasoning.get("effort"))
    return None


def _temperature(sampling_config: dict[str, Any] | None) -> float | None:
    value = (sampling_config or {}).get("temperature")
    return _optional_float(value)


def _unique_non_none(values: Any) -> Any:
    sentinel = object()
    found = sentinel
    for value in values:
        if value is None:
            continue
        if found is sentinel:
            found = value
        elif found != value:
            return None
    return None if found is sentinel else found


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    return value if isinstance(value, dict) else None


def _read_text_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(errors="replace")


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def _int_or_zero(value: Any) -> int:
    return int(value) if value is not None else 0


def _float_or_zero(value: Any) -> float:
    return float(value) if value is not None else 0.0


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _optional_str(value: object | None) -> str | None:
    return str(value) if value is not None else None

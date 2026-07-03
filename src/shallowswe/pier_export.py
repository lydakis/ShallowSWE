from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .results import RolloutResult
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

        agent_result = trial.get("agent_result") or {}
        if not isinstance(agent_result, dict):
            agent_result = {}

        rows.append(
            RolloutResult(
                model=model,
                task_id=task.task_id,
                category=task.category,
                tier=task.tier,
                rollout=rollout,
                passed=_passed(trial),
                input_tokens=_int_or_zero(agent_result.get("n_input_tokens")),
                output_tokens=_int_or_zero(agent_result.get("n_output_tokens")),
                cache_tokens=_int_or_zero(agent_result.get("n_cache_tokens")),
                cost_usd=_float_or_zero(agent_result.get("cost_usd")),
                turns=_turns(trial, agent_result),
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
    agent = trial.get("agent_info") or {}
    if not isinstance(agent, dict):
        return "unknown"
    model = agent.get("model_info")
    if isinstance(model, dict) and model.get("name"):
        return str(model["name"])
    return str(agent.get("name") or "unknown")


def _passed(trial: dict[str, Any]) -> bool:
    verifier = trial.get("verifier_result") or {}
    if not isinstance(verifier, dict):
        return False
    rewards = verifier.get("rewards") or {}
    if not isinstance(rewards, dict):
        return False
    return _float_or_zero(rewards.get("reward")) >= 1.0


def _turns(trial: dict[str, Any], agent_result: dict[str, Any]) -> int:
    return _int_or_zero(trial.get("n_agent_steps") or agent_result.get("n_agent_steps"))


def _int_or_zero(value: Any) -> int:
    return int(value) if value is not None else 0


def _float_or_zero(value: Any) -> float:
    return float(value) if value is not None else 0.0

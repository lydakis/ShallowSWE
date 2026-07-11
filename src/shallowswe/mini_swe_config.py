from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import hashlib
import json

import yaml


def load_effective_mini_swe_config(
    config_file: Path,
    *,
    base_config_file: Path | None = None,
) -> dict[str, Any]:
    if base_config_file is None:
        from minisweagent.config import builtin_config_dir

        base_config_file = builtin_config_dir / "mini.yaml"
    base = _load_mapping(base_config_file)
    override = _load_mapping(config_file)
    return recursive_merge(base, override)


def effective_scaffold_prompt_hash(config: dict[str, Any]) -> str:
    agent = config.get("agent") if isinstance(config.get("agent"), dict) else {}
    model = config.get("model") if isinstance(config.get("model"), dict) else {}
    payload = {
        "system_template": agent.get("system_template"),
        "instance_template": agent.get("instance_template"),
        "observation_template": model.get("observation_template"),
        "format_error_template": model.get("format_error_template"),
        "submission_command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"sha256:{digest}"


def recursive_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = recursive_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"mini-swe-agent config must be a mapping: {path}")
    return raw

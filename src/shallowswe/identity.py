from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import hashlib
import json


IDENTITY_SCHEMA_VERSION = "shallowswe.identity.v0.1"


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def model_config_id(config: Mapping[str, Any]) -> str:
    return _content_id("mc", config)


def agent_policy_id(policy: Mapping[str, Any], *, model_config_id: str) -> str:
    return _content_id("ap", {"model_config_id": model_config_id, **dict(policy)})


def _content_id(prefix: str, value: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(value).encode()).hexdigest()
    return f"{prefix}_sha256_{digest}"

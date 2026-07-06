from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class DispatchConfig:
    region: str | None
    account: str | None
    include_archived: bool


def load_env_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _truthy(value: str | None) -> bool:
    return value in {"1", "true", "yes", "on"}


def load_config(env_file: str | Path | None = None) -> DispatchConfig:
    values = dict(os.environ)
    if env_file is not None:
        values.update(load_env_file(env_file))

    return DispatchConfig(
        region=values.get("DISPATCH_REGION") or None,
        account=values.get("DISPATCH_ACCOUNT") or None,
        include_archived=_truthy(values.get("DISPATCH_INCLUDE_ARCHIVED")),
    )

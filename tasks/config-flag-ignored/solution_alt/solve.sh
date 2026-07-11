#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/dispatch_app/config.py" <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class DispatchConfig:
    region: str | None
    include_archived: bool


def load_env_file(path: str | Path) -> dict[str, str]:
    entries = {}
    for raw_line in Path(path).read_text().splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#"):
            key, value = stripped.split("=", 1)
            entries[key.strip()] = value.strip()
    return entries


def _truthy(value: str | None) -> bool:
    return value in {"1", "true", "yes", "on"}


def load_config(env_file: str | Path | None = None) -> DispatchConfig:
    values = {**os.environ}
    if env_file is not None:
        values |= load_env_file(env_file)
    aliases = ("DISPATCH_INCLUDE_ARCHIVED", "DISPATCH_INCLUDE_CLOSED")
    enabled = any(_truthy(values.get(name)) for name in aliases)
    return DispatchConfig(region=values.get("DISPATCH_REGION") or None, include_archived=enabled)
PY

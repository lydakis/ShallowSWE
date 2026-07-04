from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


CATEGORY_ORDER = ("fix", "transform", "operate", "invoke")
TIER_ORDER = ("t1", "t2", "t3", "t4")
VALID_CATEGORIES = set(CATEGORY_ORDER)
VALID_TIERS = set(TIER_ORDER)


@dataclass(frozen=True)
class ShallowTask:
    task_id: str
    package_name: str
    category: str
    tier: str
    language: str | None
    path: Path
    shape: str | None = None
    subtype: str | None = None
    calibration_status: str | None = None


def load_task(path: Path) -> ShallowTask:
    config_path = path / "task.toml"
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    task = raw.get("task")
    metadata = raw.get("metadata")
    if not isinstance(task, dict):
        raise ValueError(f"{config_path} missing [task]")
    if not isinstance(metadata, dict):
        raise ValueError(f"{config_path} missing [metadata]")

    package_name = str(task.get("name") or "")
    if "/" not in package_name:
        raise ValueError(f"{config_path} [task].name must use org/name format")

    category = str(metadata.get("category") or "").lower()
    tier = str(metadata.get("tier") or "").lower()
    if category not in VALID_CATEGORIES:
        raise ValueError(f"{config_path} has invalid ShallowSWE category: {category}")
    if tier not in VALID_TIERS:
        raise ValueError(f"{config_path} has invalid ShallowSWE tier: {tier}")

    return ShallowTask(
        task_id=package_name.split("/", 1)[1],
        package_name=package_name,
        category=category,
        tier=tier,
        language=str(metadata["language"]) if "language" in metadata else None,
        shape=str(metadata["shape"]) if "shape" in metadata else None,
        subtype=str(metadata["subtype"]) if "subtype" in metadata else None,
        calibration_status=(
            str(metadata["calibration_status"]) if "calibration_status" in metadata else None
        ),
        path=path,
    )


def discover_tasks(root: Path) -> list[ShallowTask]:
    return [
        load_task(path)
        for path in sorted(root.iterdir())
        if (path / "task.toml").exists()
    ]


def task_index(root: Path) -> dict[str, ShallowTask]:
    tasks = discover_tasks(root)
    index: dict[str, ShallowTask] = {}
    for task in tasks:
        index[task.task_id] = task
        index[task.package_name] = task
    return index

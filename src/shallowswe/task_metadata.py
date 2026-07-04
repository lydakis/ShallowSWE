from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


CATEGORY_ORDER = ("code", "artifact", "workflow")
SIZE_ORDER = ("small", "medium", "large")
TIER_ORDER = SIZE_ORDER
VALID_CATEGORIES = set(CATEGORY_ORDER)
VALID_SIZES = set(SIZE_ORDER)
VALID_TIERS = VALID_SIZES

LEGACY_CATEGORY_MAP = {
    "fix": "code",
    "transform": "artifact",
    "operate": "workflow",
    "invoke": "workflow",
}
LEGACY_TIER_MAP = {
    "t1": "small",
    "t2": "medium",
    "t3": "large",
    "t4": "large",
}


@dataclass(frozen=True)
class ShallowTask:
    task_id: str
    package_name: str
    category: str
    size: str
    language: str | None
    path: Path
    shape: str | None = None
    subtype: str | None = None
    calibration_status: str | None = None

    @property
    def tier(self) -> str:
        return self.size


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

    category = normalize_category(str(metadata.get("category") or "").lower())
    size = normalize_size(str(metadata.get("size") or metadata.get("tier") or "").lower())
    if category not in VALID_CATEGORIES:
        raise ValueError(f"{config_path} has invalid ShallowSWE category: {category}")
    if size not in VALID_SIZES:
        raise ValueError(f"{config_path} has invalid ShallowSWE size: {size}")

    return ShallowTask(
        task_id=package_name.split("/", 1)[1],
        package_name=package_name,
        category=category,
        size=size,
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


def normalize_category(category: str) -> str:
    return LEGACY_CATEGORY_MAP.get(category, category)


def normalize_size(size: str) -> str:
    return LEGACY_TIER_MAP.get(size, size)

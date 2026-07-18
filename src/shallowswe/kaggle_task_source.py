from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json


LAUNCH_ID_MARKER = "FROZEN_LAUNCH_UNIT_ID: str | None = None"
TASK_NAME_MARKER = 'name="shallowswe-repair-loop-v2"'


def write_bound_kaggle_task_sources(
    source_path: Path,
    launch_plan_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source = source_path.read_text()
    if source.count(LAUNCH_ID_MARKER) != 1 or source.count(TASK_NAME_MARKER) != 1:
        raise ValueError("Kaggle runner does not contain exactly one launch freeze marker pair")
    launch_plan = json.loads(launch_plan_path.read_text())
    plan_class = launch_plan.get("plan_class")
    allowed_status = (
        "development_ready" if plan_class == "development_shadow" else "official_ready"
    )
    if plan_class not in {"development_shadow", "official_pilot"}:
        raise ValueError(f"unsupported launch plan class: {plan_class!r}")
    ready_units = [
        unit
        for unit in launch_plan.get("units", [])
        if unit.get("launch_status") == allowed_status
    ]
    task_names = [str(unit.get("kaggle_task_name") or "") for unit in ready_units]
    if any(not name for name in task_names) or len(task_names) != len(set(task_names)):
        raise ValueError("launchable Kaggle units require unique task names")
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    for unit, task_name in zip(ready_units, task_names, strict=True):
        launch_unit_id = str(unit["launch_unit_id"])
        rendered = source.replace(
            LAUNCH_ID_MARKER,
            f"FROZEN_LAUNCH_UNIT_ID: str | None = {json.dumps(launch_unit_id)}",
        ).replace(TASK_NAME_MARKER, f"name={json.dumps(task_name)}")
        destination = output_dir / f"{task_name}.py"
        destination.write_text(rendered)
        sources.append(
            {
                "kaggle_task_name": task_name,
                "launch_unit_id": launch_unit_id,
                "model": unit["model"],
                "source_path": str(destination),
                "sha256": f"sha256:{hashlib.sha256(rendered.encode()).hexdigest()}",
            }
        )
    report = {
        "schema_version": "shallowswe.kaggle_bound_task_sources.v0.1",
        "plan_class": plan_class,
        "launch_plan": str(launch_plan_path),
        "source_count": len(sources),
        "sources": sources,
    }
    (output_dir / "bound-sources.json").write_text(json.dumps(report, indent=2) + "\n")
    return report

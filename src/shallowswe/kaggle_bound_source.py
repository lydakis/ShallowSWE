from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from .run_spec import load_run_spec


RUN_UNIT_MARKER = "FROZEN_RUN_UNIT_ID: str | None = None"
TASK_NAME_MARKER = 'name="shallowswe-repair-loop-v2"'


def write_bound_kaggle_task_sources(
    source_path: Path,
    run_spec_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source = source_path.read_text()
    if source.count(RUN_UNIT_MARKER) != 1 or source.count(TASK_NAME_MARKER) != 1:
        raise ValueError("Kaggle runner does not contain exactly one run-unit marker pair")
    run_spec = load_run_spec(run_spec_path)
    units = list(run_spec["units"])
    non_kaggle_units = [unit["run_unit_id"] for unit in units if unit["runner"] != "kaggle"]
    if non_kaggle_units:
        raise ValueError(
            "Kaggle bound sources require runner='kaggle': "
            + ", ".join(non_kaggle_units)
        )
    task_names = [str(unit.get("kaggle_task_name") or "") for unit in units]
    if any(not name for name in task_names) or len(task_names) != len(set(task_names)):
        raise ValueError("Kaggle run units require unique kaggle_task_name values")

    output_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    for unit, task_name in zip(units, task_names, strict=True):
        run_unit_id = str(unit["run_unit_id"])
        rendered = source.replace(
            RUN_UNIT_MARKER,
            f"FROZEN_RUN_UNIT_ID: str | None = {json.dumps(run_unit_id)}",
        ).replace(TASK_NAME_MARKER, f"name={json.dumps(task_name)}")
        destination = output_dir / f"{task_name}.py"
        destination.write_text(rendered)
        sources.append(
            {
                "kaggle_task_name": task_name,
                "run_unit_id": run_unit_id,
                "model_config_id": unit["model_config_id"],
                "source_path": str(destination),
                "sha256": f"sha256:{hashlib.sha256(rendered.encode()).hexdigest()}",
            }
        )
    report = {
        "schema_version": "shallowswe.kaggle_bound_task_sources.v0.2",
        "run_spec_id": run_spec["run_spec_id"],
        "source_count": len(sources),
        "sources": sources,
    }
    (output_dir / "bound-sources.json").write_text(json.dumps(report, indent=2) + "\n")
    return report

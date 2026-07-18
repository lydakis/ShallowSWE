from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import hashlib
import json

from .identity import canonical_json
from .repair_policy import build_repair_policy
from .results import RepairLoopResult, aggregate_repair_loops, load_repair_loops


ANALYSIS_BUNDLE_SCHEMA_VERSION = "shallowswe.analysis_bundle.v0.1"


def build_analysis_bundle(
    rows: Iterable[RepairLoopResult],
    methodology: dict[str, Any],
) -> dict[str, Any]:
    if methodology.get("schema_version") != "shallowswe.methodology_spec.v0.1":
        raise ValueError("unsupported methodology specification")
    selected = [row for row in rows if _matches(row, methodology.get("row_selector") or {})]
    if not selected:
        raise ValueError("methodology row_selector matched no results")
    group_by = tuple(
        str(value)
        for value in methodology.get("group_by", ["model_config_id", "agent_policy_id"])
    )
    payload: dict[str, Any] = {
        "schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION,
        "methodology_spec_id": methodology.get("methodology_spec_id"),
        "selected_rows": len(selected),
        "group_by": list(group_by),
        "aggregate": aggregate_repair_loops(selected, group_by=group_by),
    }
    if methodology.get("select_repair_policy"):
        payload["repair_policy"] = build_repair_policy(selected, methodology)
    payload["analysis_bundle_sha256"] = (
        f"sha256:{hashlib.sha256(canonical_json(payload).encode()).hexdigest()}"
    )
    return payload


def write_analysis_bundle(
    rows_path: Path,
    methodology_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    report = build_analysis_bundle(
        load_repair_loops(rows_path),
        json.loads(methodology_path.read_text()),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _matches(row: RepairLoopResult, selector: dict[str, Any]) -> bool:
    for key, expected in selector.items():
        if key.startswith("metadata."):
            actual = (row.run_metadata or {}).get(key.removeprefix("metadata."))
        else:
            if not hasattr(row, key):
                raise ValueError(f"unknown row_selector field: {key}")
            actual = getattr(row, key)
        allowed = expected if isinstance(expected, list) else [expected]
        if actual not in allowed:
            return False
    return True

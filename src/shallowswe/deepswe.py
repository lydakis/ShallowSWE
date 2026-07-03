from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re
import urllib.request


DEEPSWE_LEADERBOARD_URL = (
    "https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json"
)
DEEPSWE_COMPARISON_SCHEMA_VERSION = "shallowswe.deepswe_comparison.v0.1"


def load_deepswe_leaderboard(source: str) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            return dict(json.load(response))
    return dict(json.loads(Path(source).read_text()))


def build_deepswe_comparison(
    workload_index: dict[str, Any],
    deepswe_leaderboard: dict[str, Any],
) -> dict[str, object]:
    shallow_models = list(workload_index.get("models") or [])
    deepswe_rows = _deepswe_rows(deepswe_leaderboard)
    shallow_by_key = _shallow_models_by_key(shallow_models)

    rows = []
    for deep_row in deepswe_rows:
        matches = shallow_by_key.get(_canonical_model_key(str(deep_row["model"])), [])
        for shallow in matches:
            rows.append(
                {
                    "model_config": shallow["model_config"],
                    "model": shallow["model"],
                    "reasoning_effort": shallow.get("reasoning_effort"),
                    "shallowswe_basket_cpsc": shallow.get("basket_cpsc"),
                    "shallowswe_partial_basket_cpsc": shallow.get(
                        "partial_basket_cpsc"
                    ),
                    "shallowswe_basket_tokens_per_success": shallow.get(
                        "basket_tokens_per_success"
                    ),
                    "shallowswe_covered_weight": shallow.get("covered_weight"),
                    "deepswe_config": deep_row["config"],
                    "deepswe_model": deep_row["model"],
                    "deepswe_reasoning_effort": deep_row.get("reasoning_effort"),
                    "deepswe_pass_rate": deep_row["pass_rate"],
                    "deepswe_mean_cost_usd": deep_row["mean_cost_usd"],
                    "deepswe_cpsc": deep_row["deepswe_cpsc"],
                    "deepswe_mean_input_tokens": deep_row.get("mean_input_tokens"),
                    "deepswe_mean_output_tokens": deep_row.get("mean_output_tokens"),
                }
            )

    rows.sort(
        key=lambda row: (
            _none_last(row["shallowswe_basket_cpsc"]),
            _none_last(row["deepswe_cpsc"]),
            str(row["model_config"]),
            str(row["deepswe_config"]),
        )
    )
    return {
        "schema_version": DEEPSWE_COMPARISON_SCHEMA_VERSION,
        "deepswe_source": deepswe_leaderboard.get("source", "deep-swe"),
        "deepswe_generated_at": deepswe_leaderboard.get("generated_at"),
        "shallowswe_schema_version": workload_index.get("schema_version"),
        "rows": rows,
    }


def _deepswe_rows(leaderboard: dict[str, Any]) -> list[dict[str, object]]:
    rows = leaderboard.get("rows")
    if not isinstance(rows, list):
        raise ValueError("DeepSWE leaderboard missing rows list")

    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pass_rate = _optional_float(row.get("pass_rate"))
        mean_cost = _optional_float(row.get("mean_cost_usd"))
        parsed.append(
            {
                "model": str(row["model"]),
                "config": str(row.get("config") or row["model"]),
                "reasoning_effort": row.get("reasoning_effort"),
                "pass_rate": pass_rate,
                "mean_cost_usd": mean_cost,
                "deepswe_cpsc": mean_cost / pass_rate
                if pass_rate and mean_cost is not None
                else None,
                "mean_input_tokens": _optional_float(row.get("mean_input_tokens")),
                "mean_output_tokens": _optional_float(row.get("mean_output_tokens")),
            }
        )
    return parsed


def _shallow_models_by_key(
    shallow_models: list[object],
) -> dict[str, list[dict[str, object]]]:
    models_by_key: dict[str, list[dict[str, object]]] = {}
    for item in shallow_models:
        if not isinstance(item, dict):
            continue
        key = _canonical_model_key(str(item.get("model") or item.get("model_config")))
        models_by_key.setdefault(key, []).append(item)
    return models_by_key


def _canonical_model_key(model: str) -> str:
    if "/" in model:
        model = model.rsplit("/", 1)[1]
    model = re.sub(r"\[[^\]]+\]$", "", model)
    return re.sub(r"[^a-z0-9]+", "", model.lower())


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _none_last(value: object) -> tuple[int, float]:
    if value is None:
        return (1, 0.0)
    return (0, float(value))

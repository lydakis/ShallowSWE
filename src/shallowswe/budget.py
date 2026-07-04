from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from .results import PriceCatalog, RolloutResult, rollout_cost_usd


BUDGET_SCHEMA_VERSION = "shallowswe.budget.v0.1"


@dataclass(frozen=True)
class TokenBasis:
    input_tokens: int = 10_000
    output_tokens: int = 1_000
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    peak_context_tokens: int | None = 2_000


def load_panel(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    rows = raw.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"{path} missing top-level rows array")
    return raw


def estimate_panel_budget(
    panel: dict[str, Any],
    prices: PriceCatalog,
    *,
    task_count: int,
    rollouts_per_task: int,
    token_basis: TokenBasis,
    max_budget_usd: float | None = None,
) -> dict[str, Any]:
    if task_count < 1:
        raise ValueError("task_count must be positive")
    if rollouts_per_task < 1:
        raise ValueError("rollouts_per_task must be positive")
    if max_budget_usd is not None and max_budget_usd < 0:
        raise ValueError("max_budget_usd must be non-negative")
    _validate_token_basis(token_basis)

    rows = panel.get("rows")
    if not isinstance(rows, list):
        raise ValueError("panel missing top-level rows array")

    attempts_per_row = task_count * rollouts_per_task
    row_estimates: list[dict[str, Any]] = []
    missing_price_rows: list[dict[str, Any]] = []
    priced_subset_cost = 0.0

    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise ValueError("panel row must be an object")
        row_id = str(raw_row.get("id") or raw_row.get("model") or "unknown")
        model = _panel_model_id(raw_row, panel)
        estimate_row = _rollout_for_estimate(raw_row, panel, model, token_basis)

        try:
            per_attempt_cost = rollout_cost_usd(estimate_row, prices)
        except ValueError:
            missing = {
                "id": row_id,
                "model": model,
                "upstream_provider": _optional_str(raw_row.get("upstream_provider")),
                "reasoning_effort": _optional_str(raw_row.get("reasoning_effort")),
            }
            missing_price_rows.append(missing)
            row_estimates.append(
                {
                    **missing,
                    "status": "missing_price",
                    "estimated_cost_per_attempt_usd": None,
                    "estimated_row_cost_usd": None,
                }
            )
            continue

        row_cost = per_attempt_cost * attempts_per_row
        priced_subset_cost += row_cost
        row_estimates.append(
            {
                "id": row_id,
                "model": model,
                "upstream_provider": _optional_str(raw_row.get("upstream_provider")),
                "reasoning_effort": _optional_str(raw_row.get("reasoning_effort")),
                "status": "priced",
                "estimated_cost_per_attempt_usd": per_attempt_cost,
                "estimated_row_cost_usd": row_cost,
            }
        )

    priced_rows = len(rows) - len(missing_price_rows)
    full_panel_cost = priced_subset_cost if not missing_price_rows else None
    over_budget = (
        full_panel_cost is not None
        and max_budget_usd is not None
        and full_panel_cost > max_budget_usd
    )
    return {
        "schema_version": BUDGET_SCHEMA_VERSION,
        "panel": panel.get("name"),
        "panel_status": panel.get("status"),
        "task_count": task_count,
        "rollouts_per_task": rollouts_per_task,
        "estimated_attempts_per_row": attempts_per_row,
        "estimated_total_attempts": len(rows) * attempts_per_row,
        "token_basis": asdict(token_basis),
        "rows": len(rows),
        "priced_rows": priced_rows,
        "missing_price_rows": len(missing_price_rows),
        "priced_subset_cost_usd": priced_subset_cost,
        "estimated_full_panel_cost_usd": full_panel_cost,
        "budget_limit_usd": max_budget_usd,
        "over_budget": over_budget,
        "row_estimates": row_estimates,
        "missing_prices": missing_price_rows,
    }


def _rollout_for_estimate(
    panel_row: dict[str, Any],
    panel: dict[str, Any],
    model: str,
    token_basis: TokenBasis,
) -> RolloutResult:
    return RolloutResult(
        model=model,
        task_id="budget-estimate",
        category="budget",
        size="estimate",
        rollout=0,
        passed=True,
        input_tokens=token_basis.input_tokens,
        output_tokens=token_basis.output_tokens,
        cache_read_tokens=token_basis.cache_read_tokens,
        cache_write_tokens=token_basis.cache_write_tokens,
        turns=0,
        peak_context_tokens=token_basis.peak_context_tokens,
        provider=_optional_str(panel_row.get("upstream_provider")),
        inference_gateway=_panel_gateway(panel_row, panel),
        upstream_provider=_optional_str(panel_row.get("upstream_provider")),
        requested_model=model,
        reasoning_effort=_optional_str(panel_row.get("reasoning_effort")),
    )


def _panel_model_id(row: dict[str, Any], panel: dict[str, Any]) -> str:
    gateway = _panel_gateway(row, panel)
    gateway_model_key = f"{gateway}_model" if gateway else None
    if gateway_model_key and row.get(gateway_model_key):
        return str(row[gateway_model_key])
    if row.get("openrouter_model"):
        return str(row["openrouter_model"])
    if row.get("model"):
        return str(row["model"])
    raise ValueError("panel row missing model")


def _panel_gateway(row: dict[str, Any], panel: dict[str, Any]) -> str | None:
    if row.get("inference_gateway"):
        return str(row["inference_gateway"])
    defaults = panel.get("defaults")
    if isinstance(defaults, dict) and defaults.get("inference_gateway"):
        return str(defaults["inference_gateway"])
    return None


def _validate_token_basis(token_basis: TokenBasis) -> None:
    values = [
        token_basis.input_tokens,
        token_basis.output_tokens,
        token_basis.cache_read_tokens,
        token_basis.cache_write_tokens,
    ]
    if any(value < 0 for value in values):
        raise ValueError("token counts must be non-negative")
    if token_basis.cache_read_tokens + token_basis.cache_write_tokens > token_basis.input_tokens:
        raise ValueError("cache tokens cannot exceed input tokens")
    if token_basis.peak_context_tokens is not None and token_basis.peak_context_tokens < 0:
        raise ValueError("peak_context_tokens must be non-negative")


def _optional_str(value: object | None) -> str | None:
    return str(value) if value is not None else None

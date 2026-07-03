from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
import json


RESULT_SCHEMA_VERSION = "shallowswe.result.v0.2"
SCORED_STATUS = "scored"
EXCLUDED_STATUS = "excluded"


@dataclass(frozen=True)
class RolloutResult:
    model: str
    task_id: str
    category: str
    tier: str
    rollout: int
    passed: bool
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    turns: int
    peak_context_tokens: int | None = None
    provider: str | None = None
    inference_gateway: str | None = None
    upstream_provider: str | None = None
    requested_model: str | None = None
    resolved_model: str | None = None
    model_variant: str | None = None
    reasoning_effort: str | None = None
    reasoning_tokens: int = 0
    temperature: float | None = None
    sampling_config: dict[str, Any] | None = None
    gateway_reported_cost_usd: float | None = None
    agent: str | None = None
    agent_version: str | None = None
    runner: str | None = None
    runner_version: str | None = None
    scaffold_prompt_hash: str | None = None
    token_source: str | None = None
    status: str = SCORED_STATUS
    exclusion_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    schema_version: str = RESULT_SCHEMA_VERSION

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def is_scored(self) -> bool:
        return self.status != EXCLUDED_STATUS

    @property
    def model_config(self) -> str:
        if self.reasoning_effort:
            return f"{self.model}[{self.reasoning_effort}]"
        return self.model


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m: float
    cached_input_per_1m: float | None
    output_per_1m: float
    cache_write_per_1m: float | None = None
    provider: str | None = None
    gateway: str | None = None
    long_context_threshold_tokens: int | None = None
    long_context_input_per_1m: float | None = None
    long_context_cached_input_per_1m: float | None = None
    long_context_output_per_1m: float | None = None


def load_results(path: Path) -> list[RolloutResult]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON array of rollout result rows")
    return [row_from_mapping(row) for row in raw]


def dump_results(rows: Iterable[RolloutResult]) -> str:
    return json.dumps([asdict(row) for row in rows], indent=2) + "\n"


def row_from_mapping(row: dict[str, object]) -> RolloutResult:
    required = {
        "model",
        "task_id",
        "category",
        "tier",
        "rollout",
        "passed",
        "input_tokens",
        "output_tokens",
        "turns",
    }
    missing = sorted(required - row.keys())
    if missing:
        raise ValueError(f"result row missing required fields: {', '.join(missing)}")

    return RolloutResult(
        model=str(row["model"]),
        task_id=str(row["task_id"]),
        category=str(row["category"]),
        tier=str(row["tier"]),
        rollout=int(row["rollout"]),
        passed=bool(row["passed"]),
        input_tokens=int(row["input_tokens"]),
        output_tokens=int(row["output_tokens"]),
        cache_read_tokens=int(row.get("cache_read_tokens", row.get("cache_tokens", 0))),
        cache_write_tokens=int(row.get("cache_write_tokens", 0)),
        turns=int(row["turns"]),
        peak_context_tokens=_optional_int(row.get("peak_context_tokens")),
        provider=_optional_str(row.get("provider")),
        inference_gateway=_optional_str(row.get("inference_gateway")),
        upstream_provider=_optional_str(row.get("upstream_provider")),
        requested_model=_optional_str(row.get("requested_model")),
        resolved_model=_optional_str(row.get("resolved_model")),
        model_variant=_optional_str(row.get("model_variant")),
        reasoning_effort=_optional_str(row.get("reasoning_effort")),
        reasoning_tokens=int(row.get("reasoning_tokens", 0)),
        temperature=_optional_float(row.get("temperature")),
        sampling_config=_optional_dict(row.get("sampling_config")),
        gateway_reported_cost_usd=_optional_float(row.get("gateway_reported_cost_usd")),
        agent=_optional_str(row.get("agent")),
        agent_version=_optional_str(row.get("agent_version")),
        runner=_optional_str(row.get("runner")),
        runner_version=_optional_str(row.get("runner_version")),
        scaffold_prompt_hash=_optional_str(row.get("scaffold_prompt_hash")),
        token_source=_optional_str(row.get("token_source")),
        status=str(row.get("status") or SCORED_STATUS),
        exclusion_reason=_optional_str(row.get("exclusion_reason")),
        started_at=_optional_str(row.get("started_at")),
        finished_at=_optional_str(row.get("finished_at")),
        schema_version=str(row.get("schema_version") or RESULT_SCHEMA_VERSION),
    )


def load_prices(path: Path) -> dict[str, ModelPrice]:
    raw = json.loads(path.read_text())
    models = raw.get("models")
    if not isinstance(models, dict):
        raise ValueError(f"{path} missing top-level models object")

    prices: dict[str, ModelPrice] = {}
    for model, value in models.items():
        if not isinstance(value, dict):
            raise ValueError(f"{path} model {model!r} must be an object")
        provider = _optional_str(value.get("provider"))
        price = ModelPrice(
            input_per_1m=float(value["input_per_1m"]),
            cached_input_per_1m=_optional_float(value.get("cached_input_per_1m")),
            output_per_1m=float(value["output_per_1m"]),
            cache_write_per_1m=_optional_float(value.get("cache_write_per_1m")),
            provider=provider,
            gateway=_optional_str(raw.get("gateway") or value.get("gateway") or provider),
            long_context_threshold_tokens=_optional_int(
                value.get("long_context_threshold_tokens")
            ),
            long_context_input_per_1m=_optional_float(
                value.get("long_context_input_per_1m")
            ),
            long_context_cached_input_per_1m=_optional_float(
                value.get("long_context_cached_input_per_1m")
            ),
            long_context_output_per_1m=_optional_float(
                value.get("long_context_output_per_1m")
            ),
        )
        prices[str(model)] = price
        for alias in value.get("aliases", []):
            prices[str(alias)] = price
    return prices


def aggregate_results(
    rows: Iterable[RolloutResult],
    group_by: tuple[str, ...] = ("model_config", "category", "tier"),
    prices: dict[str, ModelPrice] | None = None,
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[RolloutResult]] = defaultdict(list)
    for row in rows:
        grouped[tuple(getattr(row, field) for field in group_by)].append(row)

    summaries: list[dict[str, object]] = []
    for key, group in sorted(grouped.items()):
        scored = [row for row in group if row.is_scored]
        attempts = len(scored)
        excluded_attempts = len(group) - attempts
        passes = sum(1 for row in scored if row.passed)
        pass_rate = passes / attempts if attempts else 0.0
        mean_tokens = sum(row.total_tokens for row in scored) / attempts if attempts else 0.0
        mean_input_tokens = (
            sum(row.input_tokens for row in scored) / attempts if attempts else 0.0
        )
        mean_output_tokens = (
            sum(row.output_tokens for row in scored) / attempts if attempts else 0.0
        )
        mean_cache_read_tokens = (
            sum(row.cache_read_tokens for row in scored) / attempts if attempts else 0.0
        )
        mean_cache_write_tokens = (
            sum(row.cache_write_tokens for row in scored) / attempts if attempts else 0.0
        )
        mean_reasoning_tokens = (
            sum(row.reasoning_tokens for row in scored) / attempts if attempts else 0.0
        )
        mean_turns = sum(row.turns for row in scored) / attempts if attempts else 0.0
        mean_cost = _mean_cost(scored, prices) if prices and scored else None
        cost_reconciliation = _cost_reconciliation(scored, prices) if prices and scored else None

        summary: dict[str, object] = dict(zip(group_by, key, strict=True))
        summary.update(
            {
                "total_trials": len(group),
                "attempts": attempts,
                "excluded_attempts": excluded_attempts,
                "passes": passes,
                "pass_rate": pass_rate,
                "mean_tokens_per_attempt": mean_tokens,
                "tokens_per_success": mean_tokens / pass_rate if pass_rate else None,
                "mean_input_tokens_per_attempt": mean_input_tokens,
                "mean_output_tokens_per_attempt": mean_output_tokens,
                "mean_cache_read_tokens_per_attempt": mean_cache_read_tokens,
                "mean_cache_write_tokens_per_attempt": mean_cache_write_tokens,
                "mean_reasoning_tokens_per_attempt": mean_reasoning_tokens,
                "mean_turns": mean_turns,
            }
        )
        if mean_cost is not None:
            summary.update(
                {
                    "mean_cost_per_attempt": mean_cost,
                    "cpsc": mean_cost / pass_rate if pass_rate else None,
                }
            )
            if cost_reconciliation is not None:
                summary.update(cost_reconciliation)
        summaries.append(summary)

    return summaries


def rollout_cost_usd(row: RolloutResult, prices: dict[str, ModelPrice]) -> float:
    price = _price_for_row(row, prices)
    input_rate, cached_rate, output_rate = _rates_for_row(row, price)
    cache_read = max(0, row.cache_read_tokens)
    cache_write = max(0, row.cache_write_tokens)
    uncached_input = max(0, row.input_tokens - cache_read - cache_write)

    cache_write_rate = (
        price.cache_write_per_1m
        if price.cache_write_per_1m is not None
        else input_rate
    )
    return (
        uncached_input * input_rate
        + cache_read * cached_rate
        + cache_write * cache_write_rate
        + row.output_tokens * output_rate
    ) / 1_000_000


def _mean_cost(
    rows: list[RolloutResult],
    prices: dict[str, ModelPrice] | None,
) -> float | None:
    if not prices:
        return None
    return sum(rollout_cost_usd(row, prices) for row in rows) / len(rows)


def _cost_reconciliation(
    rows: list[RolloutResult],
    prices: dict[str, ModelPrice] | None,
) -> dict[str, object] | None:
    if not prices:
        return None
    reported_rows = [
        row for row in rows if row.gateway_reported_cost_usd is not None
    ]
    if not reported_rows:
        return None

    derived_total = sum(rollout_cost_usd(row, prices) for row in reported_rows)
    reported_total = sum(row.gateway_reported_cost_usd or 0.0 for row in reported_rows)
    delta = derived_total - reported_total
    return {
        "gateway_reported_attempts": len(reported_rows),
        "mean_gateway_reported_cost_per_attempt": reported_total / len(reported_rows),
        "mean_cost_delta_vs_gateway_per_attempt": delta / len(reported_rows),
        "cost_delta_vs_gateway_ratio": (
            delta / reported_total if reported_total else None
        ),
    }


def _price_for_row(row: RolloutResult, prices: dict[str, ModelPrice]) -> ModelPrice:
    candidates = [
        row.model,
        row.resolved_model,
        _strip_openai_prefix(row.model),
        _strip_openai_prefix(row.resolved_model),
    ]
    for candidate in candidates:
        if candidate and candidate in prices and _price_matches_gateway(row, prices[candidate]):
            return prices[candidate]
    raise ValueError(f"no price found for model {row.model!r}")


def _price_matches_gateway(row: RolloutResult, price: ModelPrice) -> bool:
    if row.inference_gateway is None or price.gateway is None:
        return True
    return row.inference_gateway == price.gateway


def _rates_for_row(row: RolloutResult, price: ModelPrice) -> tuple[float, float, float]:
    use_long_context = (
        price.long_context_threshold_tokens is not None
        and row.peak_context_tokens is not None
        and row.peak_context_tokens > price.long_context_threshold_tokens
    )
    if use_long_context:
        input_rate = price.long_context_input_per_1m or price.input_per_1m
        cached_rate = (
            price.long_context_cached_input_per_1m
            if price.long_context_cached_input_per_1m is not None
            else price.cached_input_per_1m
        )
        output_rate = price.long_context_output_per_1m or price.output_per_1m
    else:
        input_rate = price.input_per_1m
        cached_rate = price.cached_input_per_1m
        output_rate = price.output_per_1m

    return (
        input_rate,
        cached_rate if cached_rate is not None else input_rate,
        output_rate,
    )


def _strip_openai_prefix(value: str | None) -> str | None:
    if value and value.startswith("openai/"):
        return value.split("/", 1)[1]
    return value


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _optional_dict(value: object | None) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _optional_str(value: object | None) -> str | None:
    return str(value) if value is not None else None

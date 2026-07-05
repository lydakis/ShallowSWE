from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from .task_metadata import normalize_category, normalize_size


RESULT_SCHEMA_VERSION = "shallowswe.result.v0.4"
REPAIR_LOOP_SCHEMA_VERSION = "shallowswe.repair_loop.v0.2"
SCORED_STATUS = "scored"
EXCLUDED_STATUS = "excluded"
CAP_HIT_STOP_REASONS = frozenset(
    {
        "dollar_cap",
        "submission_cap",
        "verifier_submission_cap",
        "step_cap",
        "agent_step_cap",
        "wall_time_cap",
    }
)


@dataclass(frozen=True)
class RolloutResult:
    model: str
    task_id: str
    category: str
    size: str
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
    task_version: str | None = None
    task_suite_version: str | None = None
    verifier_hash: str | None = None
    environment_image_digest: str | None = None
    repo_commit_sha: str | None = None
    price_sheet_version: str | None = None
    price_sheet_date: str | None = None
    seed: int | None = None
    run_id: str | None = None
    task_visibility: str | None = None
    transcript_hash: str | None = None
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

    @property
    def tier(self) -> str:
        return self.size


@dataclass(frozen=True)
class RepairLoopResult:
    model: str
    task_id: str
    category: str
    size: str
    loop: int
    passed: bool
    stop_reason: str
    verifier_submissions: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    turns: int
    agent_steps: int | None = None
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
    task_version: str | None = None
    task_suite_version: str | None = None
    verifier_hash: str | None = None
    environment_image_digest: str | None = None
    repo_commit_sha: str | None = None
    price_sheet_version: str | None = None
    price_sheet_date: str | None = None
    seed: int | None = None
    run_id: str | None = None
    task_visibility: str | None = None
    transcript_hash: str | None = None
    status: str = SCORED_STATUS
    exclusion_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    schema_version: str = REPAIR_LOOP_SCHEMA_VERSION

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def is_scored(self) -> bool:
        if self.stop_reason == "wall_time_cap":
            return True
        return self.status != EXCLUDED_STATUS

    @property
    def model_config(self) -> str:
        if self.reasoning_effort:
            return f"{self.model}[{self.reasoning_effort}]"
        return self.model

    @property
    def tier(self) -> str:
        return self.size

    @property
    def hit_scored_cap(self) -> bool:
        return self.stop_reason in CAP_HIT_STOP_REASONS


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


UsageRow = RolloutResult | RepairLoopResult
PriceEntry = ModelPrice | list[ModelPrice]
PriceCatalog = Mapping[str, PriceEntry]


def load_results(path: Path) -> list[RolloutResult]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON array of rollout result rows")
    return [row_from_mapping(row) for row in raw]


def dump_results(rows: Iterable[RolloutResult]) -> str:
    return json.dumps([asdict(row) for row in rows], indent=2) + "\n"


def load_repair_loops(path: Path) -> list[RepairLoopResult]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON array of repair-loop result rows")
    return [repair_loop_from_mapping(row) for row in raw]


def dump_repair_loops(rows: Iterable[RepairLoopResult]) -> str:
    return json.dumps([asdict(row) for row in rows], indent=2) + "\n"


def row_from_mapping(row: dict[str, object]) -> RolloutResult:
    required = {
        "model",
        "task_id",
        "category",
        "rollout",
        "passed",
        "input_tokens",
        "output_tokens",
        "turns",
    }
    if "size" not in row and "tier" not in row:
        required.add("size")
    missing = sorted(required - row.keys())
    if missing:
        raise ValueError(f"result row missing required fields: {', '.join(missing)}")

    return RolloutResult(
        model=str(row["model"]),
        task_id=str(row["task_id"]),
        category=normalize_category(str(row["category"]).lower()),
        size=normalize_size(str(row.get("size", row.get("tier"))).lower()),
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
        task_version=_optional_str(row.get("task_version")),
        task_suite_version=_optional_str(row.get("task_suite_version")),
        verifier_hash=_optional_str(row.get("verifier_hash")),
        environment_image_digest=_optional_str(row.get("environment_image_digest")),
        repo_commit_sha=_optional_str(row.get("repo_commit_sha")),
        price_sheet_version=_optional_str(row.get("price_sheet_version")),
        price_sheet_date=_optional_str(row.get("price_sheet_date")),
        seed=_optional_int(row.get("seed")),
        run_id=_optional_str(row.get("run_id")),
        task_visibility=_optional_str(row.get("task_visibility")),
        transcript_hash=_optional_str(row.get("transcript_hash")),
        status=str(row.get("status") or SCORED_STATUS),
        exclusion_reason=_optional_str(row.get("exclusion_reason")),
        started_at=_optional_str(row.get("started_at")),
        finished_at=_optional_str(row.get("finished_at")),
        schema_version=str(row.get("schema_version") or RESULT_SCHEMA_VERSION),
    )


def repair_loop_from_mapping(row: dict[str, object]) -> RepairLoopResult:
    required = {
        "model",
        "task_id",
        "category",
        "loop",
        "passed",
        "stop_reason",
        "verifier_submissions",
        "input_tokens",
        "output_tokens",
        "turns",
    }
    if "size" not in row and "tier" not in row:
        required.add("size")
    missing = sorted(required - row.keys())
    if missing:
        raise ValueError(f"repair-loop row missing required fields: {', '.join(missing)}")

    return RepairLoopResult(
        model=str(row["model"]),
        task_id=str(row["task_id"]),
        category=normalize_category(str(row["category"]).lower()),
        size=normalize_size(str(row.get("size", row.get("tier"))).lower()),
        loop=int(row["loop"]),
        passed=bool(row["passed"]),
        stop_reason=str(row["stop_reason"]),
        verifier_submissions=int(row["verifier_submissions"]),
        input_tokens=int(row["input_tokens"]),
        output_tokens=int(row["output_tokens"]),
        cache_read_tokens=int(row.get("cache_read_tokens", row.get("cache_tokens", 0))),
        cache_write_tokens=int(row.get("cache_write_tokens", 0)),
        turns=int(row["turns"]),
        agent_steps=_optional_int(row.get("agent_steps")),
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
        task_version=_optional_str(row.get("task_version")),
        task_suite_version=_optional_str(row.get("task_suite_version")),
        verifier_hash=_optional_str(row.get("verifier_hash")),
        environment_image_digest=_optional_str(row.get("environment_image_digest")),
        repo_commit_sha=_optional_str(row.get("repo_commit_sha")),
        price_sheet_version=_optional_str(row.get("price_sheet_version")),
        price_sheet_date=_optional_str(row.get("price_sheet_date")),
        seed=_optional_int(row.get("seed")),
        run_id=_optional_str(row.get("run_id")),
        task_visibility=_optional_str(row.get("task_visibility")),
        transcript_hash=_optional_str(row.get("transcript_hash")),
        status=str(row.get("status") or SCORED_STATUS),
        exclusion_reason=_optional_str(row.get("exclusion_reason")),
        started_at=_optional_str(row.get("started_at")),
        finished_at=_optional_str(row.get("finished_at")),
        schema_version=str(row.get("schema_version") or REPAIR_LOOP_SCHEMA_VERSION),
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


def merge_prices(*catalogs: Mapping[str, ModelPrice]) -> dict[str, PriceEntry]:
    merged: dict[str, PriceEntry] = {}
    for catalog in catalogs:
        for model, price in catalog.items():
            existing = merged.get(model)
            if existing is None:
                merged[model] = price
            elif isinstance(existing, list):
                if price not in existing:
                    existing.append(price)
            elif existing != price:
                merged[model] = [existing, price]
    return merged


def aggregate_results(
    rows: Iterable[RolloutResult],
    group_by: tuple[str, ...] = ("model_config", "category", "size"),
    prices: PriceCatalog | None = None,
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


def aggregate_repair_loops(
    rows: Iterable[RepairLoopResult],
    group_by: tuple[str, ...] = ("model_config", "category", "size"),
    prices: PriceCatalog | None = None,
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[RepairLoopResult]] = defaultdict(list)
    for row in rows:
        grouped[tuple(getattr(row, field) for field in group_by)].append(row)

    summaries: list[dict[str, object]] = []
    for key, group in sorted(grouped.items()):
        scored = [row for row in group if row.is_scored]
        successful = [row for row in scored if row.passed]
        repair_loops = len(scored)
        excluded_loops = len(group) - repair_loops
        successes = len(successful)
        solve_rate = successes / repair_loops if repair_loops else 0.0
        cap_hits = sum(1 for row in scored if row.hit_scored_cap)

        total_tokens = sum(row.total_tokens for row in scored)
        successful_tokens = sum(row.total_tokens for row in successful)
        total_verifier_submissions = sum(row.verifier_submissions for row in scored)
        successful_verifier_submissions = sum(row.verifier_submissions for row in successful)
        agent_step_rows = [row for row in scored if row.agent_steps is not None]

        summary: dict[str, object] = dict(zip(group_by, key, strict=True))
        summary.update(
            {
                "total_trials": len(group),
                "repair_loops": repair_loops,
                "excluded_repair_loops": excluded_loops,
                "successes": successes,
                "solve_rate": solve_rate,
                "cap_hits": cap_hits,
                "cap_hit_rate": cap_hits / repair_loops if repair_loops else 0.0,
                "mean_tokens_per_repair_loop": (
                    total_tokens / repair_loops if repair_loops else 0.0
                ),
                "tokens_per_success": total_tokens / successes if successes else None,
                "conditional_tokens_among_solved_loops": (
                    successful_tokens / successes if successes else None
                ),
                "mean_tokens_per_solved_task": (
                    successful_tokens / successes if successes else None
                ),
                "mean_input_tokens_per_repair_loop": (
                    sum(row.input_tokens for row in scored) / repair_loops
                    if repair_loops
                    else 0.0
                ),
                "mean_output_tokens_per_repair_loop": (
                    sum(row.output_tokens for row in scored) / repair_loops
                    if repair_loops
                    else 0.0
                ),
                "mean_cache_read_tokens_per_repair_loop": (
                    sum(row.cache_read_tokens for row in scored) / repair_loops
                    if repair_loops
                    else 0.0
                ),
                "mean_cache_write_tokens_per_repair_loop": (
                    sum(row.cache_write_tokens for row in scored) / repair_loops
                    if repair_loops
                    else 0.0
                ),
                "mean_reasoning_tokens_per_repair_loop": (
                    sum(row.reasoning_tokens for row in scored) / repair_loops
                    if repair_loops
                    else 0.0
                ),
                "mean_turns_per_repair_loop": (
                    sum(row.turns for row in scored) / repair_loops
                    if repair_loops
                    else 0.0
                ),
                "p95_turns_per_repair_loop": (
                    _percentile([float(row.turns) for row in scored], 0.95)
                    if repair_loops
                    else 0.0
                ),
                "mean_agent_steps_per_repair_loop": (
                    sum(row.agent_steps or 0 for row in agent_step_rows) / len(agent_step_rows)
                    if agent_step_rows
                    else None
                ),
                "p95_agent_steps_per_repair_loop": (
                    _percentile([float(row.agent_steps or 0) for row in agent_step_rows], 0.95)
                    if agent_step_rows
                    else None
                ),
                "mean_verifier_submissions_per_repair_loop": (
                    total_verifier_submissions / repair_loops if repair_loops else 0.0
                ),
                "mean_verifier_submissions_to_success": (
                    successful_verifier_submissions / successes if successes else None
                ),
                "stop_reasons": _count_stop_reasons(scored),
            }
        )
        if prices and scored:
            row_costs = [repair_loop_cost_usd(row, prices) for row in scored]
            successful_costs = [repair_loop_cost_usd(row, prices) for row in successful]
            total_cost = sum(row_costs)
            successful_cost = sum(successful_costs)
            summary.update(
                {
                    "total_model_spend_usd": total_cost,
                    "mean_cost_per_repair_loop": total_cost / repair_loops,
                    "p95_cost_per_repair_loop": _percentile(row_costs, 0.95),
                    "cpsc": total_cost / successes if successes else None,
                    "conditional_spend_among_solved_loops": (
                        successful_cost / successes if successes else None
                    ),
                    "mean_spend_per_solved_task": (
                        successful_cost / successes if successes else None
                    ),
                }
            )
            cost_reconciliation = _cost_reconciliation(
                scored,
                prices,
                unit_name="repair_loop",
                unit_plural="repair_loops",
            )
            if cost_reconciliation is not None:
                summary.update(cost_reconciliation)
        summaries.append(summary)

    return summaries


def rollout_cost_usd(row: UsageRow, prices: PriceCatalog) -> float:
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


def repair_loop_cost_usd(row: RepairLoopResult, prices: PriceCatalog) -> float:
    return rollout_cost_usd(row, prices)


def _mean_cost(
    rows: list[UsageRow],
    prices: PriceCatalog | None,
) -> float | None:
    if not prices:
        return None
    return sum(rollout_cost_usd(row, prices) for row in rows) / len(rows)


def _cost_reconciliation(
    rows: list[UsageRow],
    prices: PriceCatalog | None,
    unit_name: str = "attempt",
    unit_plural: str = "attempts",
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
        f"gateway_reported_{unit_plural}": len(reported_rows),
        f"mean_gateway_reported_cost_per_{unit_name}": reported_total / len(reported_rows),
        f"mean_cost_delta_vs_gateway_per_{unit_name}": delta / len(reported_rows),
        "cost_delta_vs_gateway_ratio": (
            delta / reported_total if reported_total else None
        ),
    }


def _price_for_row(row: UsageRow, prices: PriceCatalog) -> ModelPrice:
    candidates = [
        row.model,
        row.resolved_model,
        _strip_openai_prefix(row.model),
        _strip_openai_prefix(row.resolved_model),
    ]
    for candidate in candidates:
        for price in _price_candidates(prices, candidate):
            if _price_matches_gateway(row, price):
                return price
    raise ValueError(f"no price found for model {row.model!r}")


def _price_candidates(prices: PriceCatalog, candidate: str | None) -> tuple[ModelPrice, ...]:
    if not candidate:
        return ()
    entry = prices.get(candidate)
    if entry is None:
        return ()
    if isinstance(entry, list):
        return tuple(entry)
    return (entry,)


def _price_matches_gateway(row: UsageRow, price: ModelPrice) -> bool:
    if row.inference_gateway is None or price.gateway is None:
        return True
    return row.inference_gateway == price.gateway


def _rates_for_row(row: UsageRow, price: ModelPrice) -> tuple[float, float, float]:
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


def _count_stop_reasons(rows: list[RepairLoopResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.stop_reason] = counts.get(row.stop_reason, 0) + 1
    return dict(sorted(counts.items()))


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if quantile < 0 or quantile > 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * quantile + 0.999999)))
    return ordered[index]

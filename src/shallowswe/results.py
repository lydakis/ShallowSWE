from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import inf
from pathlib import Path
from typing import Iterable
import json


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
    cache_tokens: int
    cost_usd: float
    turns: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def load_results(path: Path) -> list[RolloutResult]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON array of rollout result rows")
    return [row_from_mapping(row) for row in raw]


def dump_results(rows: Iterable[RolloutResult]) -> str:
    return json.dumps([row.__dict__ for row in rows], indent=2) + "\n"


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
        "cache_tokens",
        "cost_usd",
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
        cache_tokens=int(row["cache_tokens"]),
        cost_usd=float(row["cost_usd"]),
        turns=int(row["turns"]),
    )


def aggregate_results(
    rows: Iterable[RolloutResult],
    group_by: tuple[str, ...] = ("model", "category", "tier"),
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[RolloutResult]] = defaultdict(list)
    for row in rows:
        grouped[tuple(getattr(row, field) for field in group_by)].append(row)

    summaries: list[dict[str, object]] = []
    for key, group in sorted(grouped.items()):
        attempts = len(group)
        passes = sum(1 for row in group if row.passed)
        pass_rate = passes / attempts if attempts else 0.0
        mean_cost = sum(row.cost_usd for row in group) / attempts
        mean_tokens = sum(row.total_tokens for row in group) / attempts
        mean_turns = sum(row.turns for row in group) / attempts

        summary: dict[str, object] = dict(zip(group_by, key, strict=True))
        summary.update(
            {
                "attempts": attempts,
                "passes": passes,
                "pass_rate": pass_rate,
                "mean_cost_per_attempt": mean_cost,
                "cpsc": mean_cost / pass_rate if pass_rate else inf,
                "mean_tokens_per_attempt": mean_tokens,
                "tokens_per_success": mean_tokens / pass_rate if pass_rate else inf,
                "mean_turns": mean_turns,
            }
        )
        summaries.append(summary)

    return summaries

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    account: str
    kind: str
    amount: float

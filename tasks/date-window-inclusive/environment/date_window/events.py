from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import csv
from pathlib import Path
@dataclass(frozen=True)
class Event:
    event_id: str
    occurred_on: date
    kind: str
def load_events(path: str | Path) -> list[Event]:
    with Path(path).open(newline="") as handle:
        return [Event(row["event_id"], date.fromisoformat(row["occurred_on"]), row["kind"]) for row in csv.DictReader(handle)]
def filter_events(events: list[Event], start_date: date, end_date: date) -> list[Event]:
    return [event for event in events if start_date <= event.occurred_on < end_date]

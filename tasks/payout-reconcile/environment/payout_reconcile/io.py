from __future__ import annotations

from pathlib import Path
import csv
import json


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: str | Path) -> list[dict[str, object]]:
    return list(json.loads(Path(path).read_text()))


def write_csv(path: str | Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

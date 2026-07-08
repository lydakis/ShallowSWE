from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

from retry_parser.scheduler import build_retry_plan


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = Path(args[0]) if args else Path("retries.csv")
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            print(json.dumps(build_retry_plan(row), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

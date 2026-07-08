from __future__ import annotations

import json
from pathlib import Path
import sys

from notifier.renderer import render_event


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = Path(args[0]) if args else Path("events.json")
    for event in json.loads(path.read_text()):
        print(json.dumps(render_event(event), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

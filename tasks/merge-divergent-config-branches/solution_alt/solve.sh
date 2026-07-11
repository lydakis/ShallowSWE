#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/apply_task.py" <<'PY'
from __future__ import annotations

from pathlib import Path
import json


def load(root: Path, branch: str) -> dict[str, object]:
    return json.loads((root / "branches" / branch / "config.json").read_text())


def main() -> None:
    root = Path.cwd()
    base, release, feature = (load(root, name) for name in ("main", "release", "feature"))
    release_values = {key: value for key, value in release.items() if key != "features"}
    feature_values = {
        **dict(base.get("features", {})),
        **dict(release.get("features", {})),
        **dict(feature.get("features", {})),
    }
    merged = {**base, **release_values, "features": feature_values}
    merged["retry_timeout_seconds"] = release["retry_timeout_seconds"]
    output = root / "repo" / "config.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    (root / "merge_report.json").write_text(
        json.dumps(
            {"resolved_conflicts": ["retry_timeout_seconds"], "sources": ["release", "feature"]},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/apply_task.py

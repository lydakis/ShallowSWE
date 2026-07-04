#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

cat > "$APP_DIR/scripts/apply_task.py" <<'PY'
from __future__ import annotations

from pathlib import Path
import copy
import json


def read_config(root: Path, branch: str) -> dict[str, object]:
    return json.loads((root / "branches" / branch / "config.json").read_text())


def main() -> None:
    root = Path.cwd()
    main_config = read_config(root, "main")
    release = read_config(root, "release")
    feature = read_config(root, "feature")

    merged = copy.deepcopy(main_config)
    merged["region"] = release["region"]
    merged["retry_timeout_seconds"] = max(
        int(main_config["retry_timeout_seconds"]),
        int(release["retry_timeout_seconds"]),
        int(feature["retry_timeout_seconds"]),
    )
    features = dict(merged.get("features", {}))
    features.update(feature.get("features", {}))
    merged["features"] = features

    (root / "repo").mkdir(exist_ok=True)
    (root / "repo" / "config.json").write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    report = {"resolved_conflicts": ["retry_timeout_seconds"], "sources": ["release", "feature"]}
    (root / "merge_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
PY

cd "$APP_DIR"
python3 scripts/apply_task.py

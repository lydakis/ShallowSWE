#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import importlib.util, os
app = Path(os.environ.get("APP_DIR", "/app"))
assert (app / "selected_commits.txt").read_text().splitlines() == ["c1-bugfix", "c3-test"]
assert not (app / "repo" / "telemetry.py").exists()
assert not (app / "repo" / "experiment.yml").exists()
assert (app / "repo" / "tests" / "test_app.py").exists()
spec = importlib.util.spec_from_file_location("repo_app", app / "repo" / "app.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
assert module.should_retry(408)
assert module.should_retry(429)
assert module.should_retry(503)
assert not module.should_retry(400)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

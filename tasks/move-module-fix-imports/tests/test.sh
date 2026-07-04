#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os, sys
app = Path(os.environ.get("APP_DIR", "/app")); sys.path.insert(0, str(app))
import app as moved_app
from text_tools.slug import slugify
from tools.slugify import slugify as old_slugify
assert slugify("Release Notes") == "release-notes"
assert old_slugify("Feature Flag") == "feature-flag"
assert moved_app.build_slug("Checkout Bug") == "checkout-bug"
assert "from text_tools.slug" in (app / "app.py").read_text()
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import os, sys, tempfile
app=Path(os.environ.get("APP_DIR","/app")); sys.path.insert(0,str(app))
from settings_cache.cache import get_feature_flags
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/"flags.json"; other=Path(tmp)/"other.json"
    p.write_text('{"search": true, "billing": false}'); other.write_text('{"search": false, "billing": true}')
    assert get_feature_flags(p) == {"search": True, "billing": False}
    p.write_text('{"search": false, "billing": true}')
    assert get_feature_flags(p) == {"search": False, "billing": True}
    assert get_feature_flags(other) == {"search": False, "billing": True}
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

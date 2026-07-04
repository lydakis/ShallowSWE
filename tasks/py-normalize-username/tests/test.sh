#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from pathlib import Path
import importlib.util

module_path = Path("/app/usernames.py")
spec = importlib.util.spec_from_file_location("usernames", module_path)
if spec is None or spec.loader is None:
    raise SystemExit("could not load /app/usernames.py")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

cases = [
    ("ALICE", "alice"),
    ("  George  ", "george"),
    ("\tMiXeD\n", "mixed"),
]

for raw, expected in cases:
    actual = module.normalize_username(raw)
    if actual != expected:
        raise SystemExit(f"normalize_username({raw!r}) returned {actual!r}, expected {expected!r}")
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"

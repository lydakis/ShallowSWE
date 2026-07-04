#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/repo/tests"

cat > "$APP_DIR/repo/__init__.py" <<'PY'
PY

cat > "$APP_DIR/repo/app.py" <<'PY'
from __future__ import annotations


RETRYABLE_EXACT_CODES = {408, 429}


def should_retry(status_code):
    return status_code in RETRYABLE_EXACT_CODES or int(status_code) >= 500
PY

cat > "$APP_DIR/repo/tests/test_app.py" <<'PY'
from repo.app import should_retry


def test_retries_timeout_rate_limit_and_server_errors():
    assert should_retry(408)
    assert should_retry(429)
    assert should_retry(503)
    assert not should_retry(400)
PY

rm -f "$APP_DIR/repo/telemetry.py" "$APP_DIR/repo/experiment.yml"
cat > "$APP_DIR/selected_commits.txt" <<'EOF'
c1-bugfix
c3-test
EOF

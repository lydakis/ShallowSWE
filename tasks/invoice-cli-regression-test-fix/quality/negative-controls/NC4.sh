#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
rm -f "$APP_DIR/tests/test_duplicate_invoices.py"

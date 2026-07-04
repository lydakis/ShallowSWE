#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ.get("APP_DIR", "/app")) / "user_export" / "exporter.py"
path.write_text(
    """import csv
import io
import json


FIELDS = ["id", "email", "name", "display_name"]


def full_name(user):
    return f"{user['first_name']} {user['last_name']}"


def row_for_user(user):
    name = full_name(user)
    return {
        "id": user["id"],
        "email": user["email"],
        "name": name,
        "display_name": name,
    }


def build_rows(users):
    return [row_for_user(user) for user in users]


def render_json(users):
    return json.dumps(build_rows(users), indent=2, sort_keys=True)


def render_csv(users):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(build_rows(users))
    return out.getvalue().strip()
"""
)
PY

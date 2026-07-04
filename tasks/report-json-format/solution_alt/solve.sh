#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import os

app = Path(os.environ.get("APP_DIR", "/app"))
serializers = app / "account_report" / "serializers.py"
text = serializers.read_text()
text = text.replace(
    "from __future__ import annotations\n\n\n",
    "from __future__ import annotations\n\nimport json\n\n\n",
)
text = text.replace(
    "\n\ndef render_report(report: dict[str, float | int | str], output_format: str) -> str:\n"
    "    if output_format == \"text\":\n"
    "        return render_text(report)\n"
    "    if output_format == \"csv\":\n"
    "        return render_csv(report)\n"
    "    raise ValueError(f\"unsupported report format: {output_format}\")\n",
    "\n\ndef render_json(report: dict[str, float | int | str]) -> str:\n"
    "    return json.dumps(dict(report), sort_keys=True)\n\n\n"
    "RENDERERS = {\"text\": render_text, \"csv\": render_csv, \"json\": render_json}\n\n\n"
    "def render_report(report: dict[str, float | int | str], output_format: str) -> str:\n"
    "    try:\n"
    "        renderer = RENDERERS[output_format]\n"
    "    except KeyError as exc:\n"
    "        raise ValueError(f\"unsupported report format: {output_format}\") from exc\n"
    "    return renderer(report)\n",
)
serializers.write_text(text)

cli = app / "account_report" / "cli.py"
cli.write_text(cli.read_text().replace('choices=["text", "csv"]', 'choices=["text", "csv", "json"]'))
PY

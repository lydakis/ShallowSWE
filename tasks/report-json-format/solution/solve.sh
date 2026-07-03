#!/usr/bin/env bash
set -euo pipefail

cd /app

python3 - <<'PY'
from pathlib import Path

serializers = Path("account_report/serializers.py")
text = serializers.read_text()
text = text.replace(
    "from __future__ import annotations\n\n\n",
    "from __future__ import annotations\n\nimport json\n\n\n",
)
text = text.replace(
    '    if output_format == "csv":\n        return render_csv(report)\n',
    '    if output_format == "csv":\n        return render_csv(report)\n'
    '    if output_format == "json":\n'
    '        return json.dumps(report, sort_keys=True)\n',
)
serializers.write_text(text)

cli = Path("account_report/cli.py")
text = cli.read_text()
text = text.replace('choices=["text", "csv"]', 'choices=["text", "csv", "json"]')
cli.write_text(text)
PY

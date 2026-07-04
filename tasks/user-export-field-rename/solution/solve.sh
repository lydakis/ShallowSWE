#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"user_export/exporter.py": "import csv, io, json\\nFIELDS=[\\"id\\",\\"email\\",\\"name\\",\\"display_name\\"]\\ndef build_rows(users):\\n    rows=[]\\n    for u in users:\\n        name=f\\"{u[\'first_name\']} {u[\'last_name\']}\\"\\n        rows.append({\\"id\\":u[\\"id\\"],\\"email\\":u[\\"email\\"],\\"name\\":name,\\"display_name\\":name})\\n    return rows\\ndef render_json(users): return json.dumps(build_rows(users), indent=2, sort_keys=True)\\ndef render_csv(users):\\n    out=io.StringIO(); writer=csv.DictWriter(out, fieldnames=FIELDS); writer.writeheader(); writer.writerows(build_rows(users)); return out.getvalue().strip()\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
PY

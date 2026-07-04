#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport csv, json\\nroot = Path.cwd(); active = churned = mrr = 0; plan_counts: dict[str, int] = {}\\nwith (root / \\"input\\" / \\"subscriptions.csv\\").open(newline=\\"\\") as handle:\\n    for row in csv.DictReader(handle):\\n        status = row[\\"status\\"]\\n        if status == \\"trialing\\": continue\\n        if status == \\"active\\": active += 1; mrr += int(row[\\"mrr\\"])\\n        elif status == \\"cancelled\\": churned += 1\\n        plan_counts[row[\\"plan\\"]] = plan_counts.get(row[\\"plan\\"], 0) + 1\\noutput = root / \\"output\\"; output.mkdir(parents=True, exist_ok=True)\\n(output / \\"summary.json\\").write_text(json.dumps({\\"active_accounts\\": active, \\"churned_accounts\\": churned, \\"mrr\\": mrr}, indent=2, sort_keys=True) + \\"\\\\n\\")\\nwith (output / \\"plan_counts.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"plan\\", \\"count\\"]); writer.writeheader()\\n    for plan in sorted(plan_counts): writer.writerow({\\"plan\\": plan, \\"count\\": plan_counts[plan]})\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport csv, json\\ndef rows(path: Path) -> list[dict[str, str]]:\\n    with path.open(newline=\\"\\") as handle: return list(csv.DictReader(handle))\\nroot = Path.cwd(); input_dir = root / \\"input\\"; invoices = {row[\\"invoice_id\\"]: row for row in rows(input_dir / \\"invoices.csv\\") if row[\\"status\\"] == \\"paid\\"}; credits: dict[str, float] = {}\\nfor credit in rows(input_dir / \\"credits.csv\\"): credits[credit[\\"invoice_id\\"]] = credits.get(credit[\\"invoice_id\\"], 0.0) + float(credit[\\"amount\\"])\\nby_plan: dict[str, dict[str, float]] = {}\\nfor invoice_id, invoice in invoices.items():\\n    bucket = by_plan.setdefault(invoice[\\"plan\\"], {\\"gross\\": 0.0, \\"credits\\": 0.0}); bucket[\\"gross\\"] += float(invoice[\\"amount\\"]); bucket[\\"credits\\"] += credits.get(invoice_id, 0.0)\\noutput = root / \\"output\\"; output.mkdir(parents=True, exist_ok=True)\\nwith (output / \\"revenue_rollup.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"plan\\", \\"gross\\", \\"credits\\", \\"net\\"]); writer.writeheader()\\n    for plan in sorted(by_plan):\\n        gross = by_plan[plan][\\"gross\\"]; credit = by_plan[plan][\\"credits\\"]; writer.writerow({\\"plan\\": plan, \\"gross\\": f\\"{gross:.2f}\\", \\"credits\\": f\\"{credit:.2f}\\", \\"net\\": f\\"{gross-credit:.2f}\\"})\\nopen_disputes = [row for row in rows(input_dir / \\"disputes.csv\\") if row[\\"status\\"] == \\"open\\"]\\nwith (output / \\"adjustments.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"dispute_id\\", \\"invoice_id\\", \\"amount\\", \\"status\\"]); writer.writeheader()\\n    for row in open_disputes: writer.writerow({\\"dispute_id\\": row[\\"dispute_id\\"], \\"invoice_id\\": row[\\"invoice_id\\"], \\"amount\\": f\\"{float(row[\'amount\']):.2f}\\", \\"status\\": row[\\"status\\"]})\\nrecognized = sum(bucket[\\"gross\\"] - bucket[\\"credits\\"] for bucket in by_plan.values())\\n(output / \\"summary.json\\").write_text(json.dumps({\\"open_disputes\\": len(open_disputes), \\"recognized_revenue\\": recognized}, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

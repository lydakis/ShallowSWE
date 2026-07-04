#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import subprocess

app = Path(os.environ.get("APP_DIR", "/app"))
files = json.loads('{"scripts/build_outputs.py": "from __future__ import annotations\\nfrom pathlib import Path\\nimport csv, json\\ndef load_rows(path: Path) -> list[dict[str, str]]:\\n    with path.open(newline=\\"\\") as handle: return list(csv.DictReader(handle))\\nroot = Path.cwd(); input_dir = root / \\"input\\"; tickets = load_rows(input_dir / \\"tickets.csv\\"); agents = {row[\\"agent_id\\"]: row[\\"name\\"] for row in load_rows(input_dir / \\"agents.csv\\")}; slas = {row[\\"priority\\"]: int(row[\\"target_minutes\\"]) for row in load_rows(input_dir / \\"slas.csv\\")}; escalations = load_rows(input_dir / \\"escalations.csv\\")\\nbreaches = []; summary_by_agent = {agent_id: {\\"agent_id\\": agent_id, \\"name\\": name, \\"tickets\\": 0, \\"sla_breaches\\": 0} for agent_id, name in agents.items()}\\nfor ticket in tickets:\\n    agent = summary_by_agent[ticket[\\"agent_id\\"]]; agent[\\"tickets\\"] += 1; target = slas[ticket[\\"priority\\"]]\\n    if int(ticket[\\"response_minutes\\"]) > target:\\n        agent[\\"sla_breaches\\"] += 1; breaches.append({\\"ticket_id\\": ticket[\\"ticket_id\\"], \\"agent_id\\": ticket[\\"agent_id\\"], \\"priority\\": ticket[\\"priority\\"], \\"response_minutes\\": ticket[\\"response_minutes\\"], \\"target_minutes\\": str(target)})\\noutput = root / \\"output\\"; output.mkdir(parents=True, exist_ok=True)\\nwith (output / \\"agent_summary.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"agent_id\\", \\"name\\", \\"tickets\\", \\"sla_breaches\\"]); writer.writeheader(); writer.writerows(summary_by_agent[key] for key in sorted(summary_by_agent))\\nwith (output / \\"sla_breaches.csv\\").open(\\"w\\", newline=\\"\\") as handle:\\n    writer = csv.DictWriter(handle, fieldnames=[\\"ticket_id\\", \\"agent_id\\", \\"priority\\", \\"response_minutes\\", \\"target_minutes\\"]); writer.writeheader(); writer.writerows(breaches)\\n(output / \\"summary.json\\").write_text(json.dumps({\\"escalations\\": len(escalations), \\"sla_breaches\\": len(breaches), \\"tickets\\": len(tickets)}, indent=2, sort_keys=True) + \\"\\\\n\\")\\n"}')
for rel, content in files.items():
    path = app / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

subprocess.run(['python3', 'scripts/build_outputs.py'], cwd=app, check=True)
PY

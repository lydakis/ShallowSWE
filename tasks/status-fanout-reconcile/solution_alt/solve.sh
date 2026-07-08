#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR/scripts"

python3 - <<'PY'
from pathlib import Path
import os

script = Path(os.environ.get("APP_DIR", "/app")) / "scripts" / "apply_task.py"
script.write_text(
    '''from __future__ import annotations

from pathlib import Path
import json


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\\n")


def status_for(result, prefix):
    commit = str(result["commit"])
    project = str(result["project"])
    suite = str(result["suite"])
    failed = [str(item) for item in result.get("failed") or []]
    flaky = [str(item) for item in result.get("flaky") or []]
    if failed:
        body = f"{project} {suite} failed on {commit}: {', '.join(failed)}"
        state = "failure"
    elif flaky:
        body = f"{project} {suite} passed on {commit}: {result['passed']} checks; flaky: {', '.join(flaky)}"
        state = "success"
    else:
        body = f"{project} {suite} passed on {commit}: {result['passed']} checks"
        state = "success"
    return {"commit": commit, "context": f"{prefix}/{project}/{suite}", "state": state, "body": body}


def owner_for(results, project, commit):
    for result in results:
        if str(result["project"]) == project and str(result["commit"]) == commit:
            return str(result.get("owner") or "unassigned")
    return "unassigned"


def channel(owner, rules):
    return str(rules.get("owner_channels", {}).get(owner, rules.get("default_channel", "#builds")))


def gate_targets(results, rules):
    by_suite = {(str(r["project"]), str(r["commit"]), str(r["suite"])): r for r in results}
    keys = sorted(
        {
            (str(r["project"]), str(env), str(r["commit"]))
            for r in results
            for env in (r.get("environments") or [])
        }
    )
    targets = []
    required = rules.get("required_suites", {})
    for project, environment, commit in keys:
        blockers = []
        for suite in required.get(project, {}).get(environment, []):
            result = by_suite.get((project, commit, suite))
            if result is None:
                blockers.append(f"missing:{suite}")
                continue
            if result.get("failed"):
                blockers.append(f"failed:{suite}")
            if result.get("flaky") and bool(result.get("blocking")):
                blockers.append(f"flaky:{suite}")
        targets.append(
            {
                "project": project,
                "environment": environment,
                "commit": commit,
                "state": "blocked" if blockers else "ready",
                "blockers": blockers,
                "updated_at": rules["report_time"],
            }
        )
    return targets


def notification_targets(results, gates, rules):
    protected = set(rules.get("protected_branches", []))
    out = {}
    for result in results:
        if result.get("branch") in protected and result.get("blocking") and result.get("failed"):
            commit = str(result["commit"])
            project = str(result["project"])
            suite = str(result["suite"])
            owner = str(result.get("owner") or "unassigned")
            key = f"result:{commit}:{project}:{suite}:failure"
            out[key] = {
                "key": key,
                "channel": channel(owner, rules),
                "owner": owner,
                "kind": "result_failure",
                "summary": f"{project}/{suite} failed on protected branch {result['branch']} for {commit}",
            }
    for gate in gates:
        if gate["environment"] == "prod" and gate["state"] == "blocked":
            owner = owner_for(results, gate["project"], gate["commit"])
            key = f"gate:{gate['project']}:{gate['environment']}:{gate['commit']}:blocked"
            out[key] = {
                "key": key,
                "channel": channel(owner, rules),
                "owner": owner,
                "kind": "gate_blocked",
                "summary": f"{gate['project']} {gate['environment']} blocked for {gate['commit']}: {', '.join(gate['blockers'])}",
            }
    return [out[key] for key in sorted(out)]


def main() -> None:
    root = Path.cwd()
    api = root / "api_state"
    results = load(root / "input" / "build_results.json", [])
    rules = load(root / "input" / "release_rules.json", {})
    calls = []

    statuses = {(r["commit"], r["context"]): r for r in load(api / "statuses.json", [])}
    status_changes = 0
    for result in results:
        target = status_for(result, str(rules.get("context_prefix", "ci")))
        key = (target["commit"], target["context"])
        current = statuses.get(key)
        if current is None:
            statuses[key] = target
            calls.append(f"post_status {target['commit']} {target['context']} {target['state']}")
            status_changes += 1
        elif current.get("state") != target["state"] or current.get("body") != target["body"]:
            statuses[key] = target
            calls.append(f"update_status {target['commit']} {target['context']} {target['state']}")
            status_changes += 1

    gates = {(g["project"], g["environment"], g["commit"]): g for g in load(api / "deployment_gates.json", [])}
    target_gates = gate_targets(results, rules)
    gate_calls = []
    for target in target_gates:
        key = (target["project"], target["environment"], target["commit"])
        current = gates.get(key)
        if current is None:
            gates[key] = target
            gate_calls.append(f"post_gate {target['project']} {target['environment']} {target['commit']} {target['state']}")
        elif current.get("state") != target["state"] or current.get("blockers") != target["blockers"] or current.get("updated_at") != target["updated_at"]:
            gates[key] = target
            gate_calls.append(f"update_gate {target['project']} {target['environment']} {target['commit']} {target['state']}")
    calls.extend(gate_calls)

    notifications = {n["key"]: n for n in load(api / "notifications.json", [])}
    new_notifications = []
    for target in notification_targets(results, target_gates, rules):
        if target["key"] not in notifications:
            notifications[target["key"]] = target
            new_notifications.append(target)
    calls.extend(f"notify {n['key']}" for n in sorted(new_notifications, key=lambda n: n["key"]))

    dump(api / "statuses.json", sorted(statuses.values(), key=lambda r: (r["commit"], r["context"])))
    dump(api / "deployment_gates.json", sorted(gates.values(), key=lambda r: (r["project"], r["environment"], r["commit"])))
    dump(api / "notifications.json", sorted(notifications.values(), key=lambda r: r["key"]))
    (api / "calls.log").write_text("\\n".join(calls) + ("\\n" if calls else ""))

    blocked = [g for g in target_gates if g["state"] == "blocked"]
    dump(
        api / "release_summary.json",
        {
            "generated_at": rules["report_time"],
            "results_seen": len(results),
            "status_updates": status_changes,
            "gate_updates": len(gate_calls),
            "notifications_sent": len(new_notifications),
            "failed_results": sum(1 for r in results if r.get("failed")),
            "blocked_gates": len(blocked),
            "ready_gates": sum(1 for g in target_gates if g["state"] == "ready"),
            "projects_with_blocked_prod": sorted({g["project"] for g in blocked if g["environment"] == "prod"}),
        },
    )


if __name__ == "__main__":
    main()
'''
)
PY

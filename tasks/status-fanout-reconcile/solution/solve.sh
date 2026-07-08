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

from collections import defaultdict
from pathlib import Path
from typing import Any
import json


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\\n")


def desired_status(result: dict[str, Any], prefix: str) -> dict[str, str]:
    commit = str(result["commit"])
    project = str(result["project"])
    suite = str(result["suite"])
    failed = [str(item) for item in result.get("failed") or []]
    flaky = [str(item) for item in result.get("flaky") or []]
    if failed:
        state = "failure"
        body = f"{project} {suite} failed on {commit}: {', '.join(failed)}"
    elif flaky:
        state = "success"
        body = f"{project} {suite} passed on {commit}: {result['passed']} checks; flaky: {', '.join(flaky)}"
    else:
        state = "success"
        body = f"{project} {suite} passed on {commit}: {result['passed']} checks"
    return {"commit": commit, "context": f"{prefix}/{project}/{suite}", "state": state, "body": body}


def status_changed(current: dict[str, Any] | None, target: dict[str, str]) -> bool:
    return current is None or current.get("state") != target["state"] or current.get("body") != target["body"]


def first_owner(results: list[dict[str, Any]], project: str, commit: str) -> str:
    for result in results:
        if str(result["project"]) == project and str(result["commit"]) == commit:
            return str(result.get("owner") or "unassigned")
    return "unassigned"


def desired_gates(results: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for result in results:
        key = (str(result["project"]), str(result["commit"]), str(result["suite"]))
        by_key[key] = result

    gate_keys: set[tuple[str, str, str]] = set()
    for result in results:
        project = str(result["project"])
        commit = str(result["commit"])
        for environment in result.get("environments") or []:
            gate_keys.add((project, str(environment), commit))

    gates: list[dict[str, Any]] = []
    required_by_project = rules.get("required_suites", {})
    for project, environment, commit in sorted(gate_keys):
        required = list(required_by_project.get(project, {}).get(environment, []))
        blockers: list[str] = []
        for suite in required:
            result = by_key.get((project, commit, suite))
            if result is None:
                blockers.append(f"missing:{suite}")
                continue
            if result.get("failed"):
                blockers.append(f"failed:{suite}")
            if result.get("flaky") and bool(result.get("blocking")):
                blockers.append(f"flaky:{suite}")
        gates.append(
            {
                "project": project,
                "environment": environment,
                "commit": commit,
                "state": "blocked" if blockers else "ready",
                "blockers": blockers,
                "updated_at": rules["report_time"],
            }
        )
    return gates


def gate_changed(current: dict[str, Any] | None, target: dict[str, Any]) -> bool:
    return (
        current is None
        or current.get("state") != target["state"]
        or current.get("blockers") != target["blockers"]
        or current.get("updated_at") != target["updated_at"]
    )


def channel_for(owner: str, rules: dict[str, Any]) -> str:
    return str(rules.get("owner_channels", {}).get(owner, rules.get("default_channel", "#builds")))


def desired_notifications(
    results: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    rules: dict[str, Any],
) -> list[dict[str, str]]:
    protected = set(rules.get("protected_branches", []))
    notifications: list[dict[str, str]] = []
    for result in results:
        failed = result.get("failed") or []
        if result.get("branch") in protected and bool(result.get("blocking")) and failed:
            owner = str(result.get("owner") or "unassigned")
            commit = str(result["commit"])
            project = str(result["project"])
            suite = str(result["suite"])
            branch = str(result["branch"])
            notifications.append(
                {
                    "key": f"result:{commit}:{project}:{suite}:failure",
                    "channel": channel_for(owner, rules),
                    "owner": owner,
                    "kind": "result_failure",
                    "summary": f"{project}/{suite} failed on protected branch {branch} for {commit}",
                }
            )
    for gate in gates:
        if gate["environment"] == "prod" and gate["state"] == "blocked":
            project = str(gate["project"])
            commit = str(gate["commit"])
            owner = first_owner(results, project, commit)
            environment = str(gate["environment"])
            notifications.append(
                {
                    "key": f"gate:{project}:{environment}:{commit}:blocked",
                    "channel": channel_for(owner, rules),
                    "owner": owner,
                    "kind": "gate_blocked",
                    "summary": f"{project} {environment} blocked for {commit}: {', '.join(gate['blockers'])}",
                }
            )
    by_key = {item["key"]: item for item in notifications}
    return [by_key[key] for key in sorted(by_key)]


def main() -> None:
    root = Path.cwd()
    api_state = root / "api_state"
    results = read_json(root / "input" / "build_results.json", [])
    rules = read_json(root / "input" / "release_rules.json", {})

    statuses = read_json(api_state / "statuses.json", [])
    status_index = {(row["commit"], row["context"]): dict(row) for row in statuses}
    calls: list[str] = []
    status_call_count = 0
    prefix = str(rules.get("context_prefix", "ci"))
    for result in results:
        target = desired_status(result, prefix)
        key = (target["commit"], target["context"])
        current = status_index.get(key)
        if current is None:
            status_index[key] = target
            calls.append(f"post_status {target['commit']} {target['context']} {target['state']}")
            status_call_count += 1
        elif status_changed(current, target):
            status_index[key] = target
            calls.append(f"update_status {target['commit']} {target['context']} {target['state']}")
            status_call_count += 1

    gates = read_json(api_state / "deployment_gates.json", [])
    gate_index = {
        (row["project"], row["environment"], row["commit"]): dict(row)
        for row in gates
    }
    targets = desired_gates(results, rules)
    gate_calls: list[str] = []
    for target in targets:
        key = (target["project"], target["environment"], target["commit"])
        current = gate_index.get(key)
        if current is None:
            gate_index[key] = target
            gate_calls.append(f"post_gate {target['project']} {target['environment']} {target['commit']} {target['state']}")
        elif gate_changed(current, target):
            gate_index[key] = target
            gate_calls.append(f"update_gate {target['project']} {target['environment']} {target['commit']} {target['state']}")
    calls.extend(gate_calls)

    notifications = read_json(api_state / "notifications.json", [])
    notification_index = {row["key"]: dict(row) for row in notifications}
    new_notifications: list[dict[str, str]] = []
    for notification in desired_notifications(results, targets, rules):
        if notification["key"] not in notification_index:
            notification_index[notification["key"]] = notification
            new_notifications.append(notification)
    calls.extend(f"notify {item['key']}" for item in sorted(new_notifications, key=lambda row: row["key"]))

    final_statuses = sorted(status_index.values(), key=lambda row: (row["commit"], row["context"]))
    final_gates = sorted(
        gate_index.values(),
        key=lambda row: (row["project"], row["environment"], row["commit"]),
    )
    final_notifications = sorted(notification_index.values(), key=lambda row: row["key"])

    write_json(api_state / "statuses.json", final_statuses)
    write_json(api_state / "deployment_gates.json", final_gates)
    write_json(api_state / "notifications.json", final_notifications)
    (api_state / "calls.log").write_text("\\n".join(calls) + ("\\n" if calls else ""))

    blocked_targets = [gate for gate in targets if gate["state"] == "blocked"]
    summary = {
        "generated_at": rules["report_time"],
        "results_seen": len(results),
        "status_updates": status_call_count,
        "gate_updates": len(gate_calls),
        "notifications_sent": len(new_notifications),
        "failed_results": sum(1 for result in results if result.get("failed")),
        "blocked_gates": len(blocked_targets),
        "ready_gates": sum(1 for gate in targets if gate["state"] == "ready"),
        "projects_with_blocked_prod": sorted(
            {gate["project"] for gate in blocked_targets if gate["environment"] == "prod"}
        ),
    }
    write_json(api_state / "release_summary.json", summary)


if __name__ == "__main__":
    main()
'''
)
PY

#!/usr/bin/env bash
set -euo pipefail

cat > release_train/reconcile.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalReleaseApi


def audit(action: str, target: str, detail: str) -> dict[str, str]:
    return {"action": action, "target": target, "detail": detail}


def checks_pass(state: dict[str, Any], sha: str, required_checks: list[str]) -> bool:
    current = state["status_checks"].get(sha, {})
    return all(current.get(check) == "passed" for check in required_checks)


def changelog_ready(lines: list[str], heading: str, required_lines: list[str]) -> bool:
    return heading in lines and all(line in lines for line in required_lines)


def is_reconciled(api: LocalReleaseApi, plan: dict[str, Any]) -> bool:
    branch = plan["release_branch"]
    required = [commit["sha"] for commit in plan["required_commits"]]
    commits = api.state["branches"][branch]["commits"]
    if any(sha not in commits for sha in required):
        return False
    if any(sha in commits for sha in plan.get("blocked_commits", [])):
        return False
    if api.state["branches"][branch]["head"] != required[-1]:
        return False
    required_checks = list(plan["required_checks"])
    if any(not checks_pass(api.state, sha, required_checks) for sha in required):
        return False
    required_lines = [commit["changelog"] for commit in plan["required_commits"]]
    if not changelog_ready(api.state["changelog"].get(branch, []), plan["changelog_heading"], required_lines):
        return False
    return api.state["tags"].get(plan["release_tag"]) == api.state["branches"][branch]["head"]


def write_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    Path(path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def reconcile_release(api: LocalReleaseApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    branch = plan["release_branch"]
    source = plan["source_branch"]
    rows: list[dict[str, str]] = []

    if is_reconciled(api, plan):
        write_rows(audit_path, [audit("noop", plan["release_tag"], "already reconciled")])
        return

    source_commits = set(api.state["branches"][source]["commits"])
    release_commits = api.state["branches"][branch]["commits"]
    blocked = set(plan.get("blocked_commits", []))

    for commit in plan["required_commits"]:
        sha = commit["sha"]
        if sha in blocked:
            continue
        if sha not in source_commits:
            raise ValueError(f"required commit not on source branch: {sha}")
        if sha not in release_commits:
            api.apply_commit(branch, sha)
            rows.append(audit("apply_commit", sha, f"applied to {branch}"))
            release_commits = api.state["branches"][branch]["commits"]

    required_checks = list(plan["required_checks"])
    for commit in plan["required_commits"]:
        sha = commit["sha"]
        for check in required_checks:
            if api.state["status_checks"].setdefault(sha, {}).get(check) != "passed":
                api.run_check(sha, check)
                rows.append(audit("run_check", f"{sha}:{check}", "marked passed"))

    required_lines = [commit["changelog"] for commit in plan["required_commits"]]
    before = list(api.state["changelog"].get(branch, []))
    if not changelog_ready(before, plan["changelog_heading"], required_lines):
        api.update_changelog(branch, plan["changelog_heading"], required_lines)
        rows.append(audit("update_changelog", branch, "added missing release notes"))

    target = api.state["branches"][branch]["head"]
    if api.state["tags"].get(plan["release_tag"]) != target:
        api.create_tag(plan["release_tag"], target)
        rows.append(audit("create_tag", plan["release_tag"], f"tagged {target}"))

    if not rows:
        rows.append(audit("noop", plan["release_tag"], "already reconciled"))
    write_rows(audit_path, rows)
PY

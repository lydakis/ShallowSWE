#!/usr/bin/env bash
set -euo pipefail

cat > release_train/reconcile.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalReleaseApi


def row(action: str, target: str, detail: str) -> dict[str, str]:
    return {"action": action, "target": target, "detail": detail}


def emit(path: str | Path, rows: list[dict[str, str]]) -> None:
    Path(path).write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in rows))


def all_checks_pass(state: dict[str, Any], commits: list[str], checks: list[str]) -> bool:
    return all(state["status_checks"].get(sha, {}).get(check) == "passed" for sha in commits for check in checks)


def notes_complete(state: dict[str, Any], branch: str, heading: str, notes: list[str]) -> bool:
    lines = state["changelog"].get(branch, [])
    return heading in lines and all(note in lines for note in notes)


def already_done(api: LocalReleaseApi, plan: dict[str, Any], required_shas: list[str], notes: list[str]) -> bool:
    branch = plan["release_branch"]
    branch_state = api.state["branches"][branch]
    if branch_state["head"] != required_shas[-1]:
        return False
    if any(sha not in branch_state["commits"] for sha in required_shas):
        return False
    if any(sha in branch_state["commits"] for sha in plan.get("blocked_commits", [])):
        return False
    if not all_checks_pass(api.state, required_shas, list(plan["required_checks"])):
        return False
    if not notes_complete(api.state, branch, plan["changelog_heading"], notes):
        return False
    return api.state["tags"].get(plan["release_tag"]) == branch_state["head"]


def reconcile_release(api: LocalReleaseApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    branch = plan["release_branch"]
    required = list(plan["required_commits"])
    required_shas = [commit["sha"] for commit in required]
    notes = [commit["changelog"] for commit in required]
    rows: list[dict[str, str]] = []

    if already_done(api, plan, required_shas, notes):
        emit(audit_path, [row("noop", plan["release_tag"], "already reconciled")])
        return

    available = set(api.state["branches"][plan["source_branch"]]["commits"])
    existing = api.state["branches"][branch]["commits"]
    blocked = set(plan.get("blocked_commits", []))
    for sha in required_shas:
        if sha in blocked:
            raise ValueError(f"blocked required commit: {sha}")
        if sha not in available:
            raise ValueError(f"missing source commit: {sha}")
        if sha not in existing:
            api.apply_commit(branch, sha)
            rows.append(row("apply_commit", sha, f"applied to {branch}"))
            existing = api.state["branches"][branch]["commits"]

    checks = list(plan["required_checks"])
    for sha in required_shas:
        check_state = api.state["status_checks"].setdefault(sha, {})
        for check in checks:
            if check_state.get(check) != "passed":
                api.run_check(sha, check)
                rows.append(row("run_check", f"{sha}:{check}", "marked passed"))
                check_state = api.state["status_checks"][sha]

    if not notes_complete(api.state, branch, plan["changelog_heading"], notes):
        api.update_changelog(branch, plan["changelog_heading"], notes)
        rows.append(row("update_changelog", branch, "added missing release notes"))

    target = api.state["branches"][branch]["head"]
    if api.state["tags"].get(plan["release_tag"]) != target:
        api.create_tag(plan["release_tag"], target)
        rows.append(row("create_tag", plan["release_tag"], f"tagged {target}"))

    emit(audit_path, rows or [row("noop", plan["release_tag"], "already reconciled")])
PY

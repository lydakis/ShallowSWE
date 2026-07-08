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


def write_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    Path(path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def required_shas(plan: dict[str, Any]) -> list[str]:
    return [commit["sha"] for commit in plan["required_commits"]]


def changelog_lines(plan: dict[str, Any]) -> list[str]:
    return [commit["changelog"] for commit in plan["required_commits"]]


def manifest_for(plan: dict[str, Any], target: str) -> dict[str, Any]:
    return {
        "release_branch": plan["release_branch"],
        "source_branch": plan["source_branch"],
        "target": target,
        "required_commits": required_shas(plan),
        "blocked_commits": list(plan.get("blocked_commits", [])),
        "required_checks": list(plan["required_checks"]),
        "promotion_rings": [ring["ring"] for ring in plan.get("promotion_rings", [])],
        "changelog_heading": plan["changelog_heading"],
    }


def promotion_for(ring: dict[str, Any], target: str) -> dict[str, Any]:
    return {
        "ring": ring["ring"],
        "target": target,
        "status": "ready",
        "approvers": list(ring["approvers"]),
        "note": ring["manifest_note"],
    }


def expected_promotions(plan: dict[str, Any], target: str) -> list[dict[str, Any]]:
    return [promotion_for(ring, target) for ring in plan.get("promotion_rings", [])]


def checks_pass(state: dict[str, Any], sha: str, checks: list[str]) -> bool:
    current = state["status_checks"].get(sha, {})
    return all(current.get(check) == "passed" for check in checks)


def changelog_ready(lines: list[str], heading: str, required_lines: list[str]) -> bool:
    return heading in lines and all(line in lines for line in required_lines)


def is_reconciled(api: LocalReleaseApi, plan: dict[str, Any]) -> bool:
    branch = plan["release_branch"]
    shas = required_shas(plan)
    branch_state = api.state["branches"][branch]
    if any(sha not in branch_state["commits"] for sha in shas):
        return False
    if any(sha in branch_state["commits"] for sha in plan.get("blocked_commits", [])):
        return False
    if branch_state["head"] != shas[-1]:
        return False
    commit_checks = list(plan["required_checks"])
    if any(not checks_pass(api.state, sha, commit_checks) for sha in shas):
        return False
    target = branch_state["head"]
    for ring in plan.get("promotion_rings", []):
        if not checks_pass(api.state, target, list(ring["required_checks"])):
            return False
    if not changelog_ready(
        api.state["changelog"].get(branch, []), plan["changelog_heading"], changelog_lines(plan)
    ):
        return False
    tag = plan["release_tag"]
    if api.state["release_manifests"].get(tag) != manifest_for(plan, target):
        return False
    if api.state["promotion_records"].get(tag) != expected_promotions(plan, target):
        return False
    return api.state["tags"].get(tag) == target


def reconcile_release(api: LocalReleaseApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    rows: list[dict[str, str]] = []
    branch = plan["release_branch"]
    tag = plan["release_tag"]

    if is_reconciled(api, plan):
        write_rows(audit_path, [audit("noop", tag, "already reconciled")])
        return

    source_commits = set(api.state["branches"][plan["source_branch"]]["commits"])
    release_commits = api.state["branches"][branch]["commits"]
    blocked = set(plan.get("blocked_commits", []))
    for sha in required_shas(plan):
        if sha in blocked:
            raise ValueError(f"required commit is blocked: {sha}")
        if sha not in source_commits:
            raise ValueError(f"required commit not on source branch: {sha}")
        if sha not in release_commits:
            api.apply_commit(branch, sha)
            rows.append(audit("apply_commit", sha, f"applied to {branch}"))
            release_commits = api.state["branches"][branch]["commits"]

    for sha in required_shas(plan):
        for check in plan["required_checks"]:
            if api.state["status_checks"].setdefault(sha, {}).get(check) != "passed":
                api.run_check(sha, check)
                rows.append(audit("run_check", f"{sha}:{check}", "marked passed"))

    target = api.state["branches"][branch]["head"]
    for ring in plan.get("promotion_rings", []):
        for check in ring["required_checks"]:
            if api.state["status_checks"].setdefault(target, {}).get(check) != "passed":
                api.run_check(target, check)
                rows.append(audit("run_check", f"{target}:{check}", "marked passed"))

    notes = changelog_lines(plan)
    if not changelog_ready(api.state["changelog"].get(branch, []), plan["changelog_heading"], notes):
        api.update_changelog(branch, plan["changelog_heading"], notes)
        rows.append(audit("update_changelog", branch, "added missing release notes"))

    manifest = manifest_for(plan, target)
    if api.state["release_manifests"].get(tag) != manifest:
        api.write_release_manifest(tag, manifest)
        rows.append(audit("write_manifest", tag, "wrote release manifest"))

    current_records = api.state["promotion_records"].get(tag, [])
    for expected in expected_promotions(plan, target):
        if expected not in current_records:
            api.record_promotion(tag, expected)
            rows.append(
                audit("record_promotion", f"{tag}:{expected['ring']}", "recorded promotion readiness")
            )
            current_records = api.state["promotion_records"].get(tag, [])

    if api.state["tags"].get(tag) != target:
        api.create_tag(tag, target)
        rows.append(audit("create_tag", tag, f"tagged {target}"))

    write_rows(audit_path, rows or [audit("noop", tag, "already reconciled")])
PY

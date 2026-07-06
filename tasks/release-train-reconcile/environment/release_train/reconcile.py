from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .api import LocalReleaseApi


def _audit(action: str, target: str, detail: str) -> dict[str, str]:
    return {"action": action, "target": target, "detail": detail}


def reconcile_release(api: LocalReleaseApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    """Naive seed implementation with intentionally incomplete release ordering."""
    rows: list[dict[str, str]] = []
    branch = plan["release_branch"]
    for commit in plan["required_commits"]:
        api.apply_commit(branch, commit["sha"])
        rows.append(_audit("apply_commit", commit["sha"], "applied required commit"))

    target = api.state["branches"][branch]["head"]
    api.create_tag(plan["release_tag"], target)
    rows.append(_audit("create_tag", plan["release_tag"], f"tagged {target}"))

    api.update_changelog(
        branch,
        plan["changelog_heading"],
        [commit["changelog"] for commit in plan["required_commits"]],
    )
    rows.append(_audit("update_changelog", branch, "updated changelog"))

    Path(audit_path).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )

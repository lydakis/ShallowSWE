from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json


class LocalReleaseApi:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = copy.deepcopy(state)
        self.state.setdefault("branches", {})
        self.state.setdefault("tags", {})
        self.state.setdefault("status_checks", {})
        self.state.setdefault("changelog", {})
        self.state.setdefault("release_manifests", {})
        self.state.setdefault("promotion_records", {})
        self.state.setdefault("call_log", [])

    @classmethod
    def load(cls, path: str | Path) -> "LocalReleaseApi":
        return cls(json.loads(Path(path).read_text()))

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n")

    def branch_commits(self, branch: str) -> list[str]:
        return list(self.state["branches"][branch]["commits"])

    def apply_commit(self, branch: str, sha: str) -> None:
        commits = self.state["branches"][branch]["commits"]
        commits.append(sha)
        self.state["branches"][branch]["head"] = sha
        self._log("apply_commit", branch, {"sha": sha})

    def run_check(self, sha: str, check: str) -> None:
        self.state["status_checks"].setdefault(sha, {})[check] = "passed"
        self._log("run_check", sha, {"check": check})

    def update_changelog(self, branch: str, heading: str, lines: list[str]) -> None:
        current = self.state["changelog"].setdefault(branch, [])
        if heading not in current:
            current.append(heading)
        required_lines = set(lines)
        current[:] = [line for line in current if line not in required_lines]
        insert_at = current.index(heading) + 1
        for line in lines:
            current.insert(insert_at, line)
            insert_at += 1
        self._log("update_changelog", branch, {"heading": heading, "lines": list(lines)})

    def write_release_manifest(self, tag: str, manifest: dict[str, Any]) -> None:
        self.state["release_manifests"][tag] = copy.deepcopy(manifest)
        self._log("write_manifest", tag, copy.deepcopy(manifest))

    def record_promotion(self, tag: str, record: dict[str, Any]) -> None:
        records = self.state["promotion_records"].setdefault(tag, [])
        records[:] = [item for item in records if item.get("ring") != record.get("ring")]
        records.append(copy.deepcopy(record))
        self._log("record_promotion", tag, copy.deepcopy(record))

    def create_tag(self, tag: str, target: str) -> None:
        self.state["tags"][tag] = target
        self._log("create_tag", tag, {"target": target})

    def delete_branch(self, branch: str) -> None:
        self.state["branches"].pop(branch, None)
        self._log("delete_branch", branch, {})

    def delete_tag(self, tag: str) -> None:
        self.state["tags"].pop(tag, None)
        self._log("delete_tag", tag, {})

    def force_update_branch(self, branch: str, commits: list[str]) -> None:
        self.state["branches"][branch]["commits"] = list(commits)
        self.state["branches"][branch]["head"] = commits[-1] if commits else ""
        self._log("force_update_branch", branch, {"commits": list(commits)})

    def reset_branch(self, branch: str, target: str) -> None:
        commits = self.state["branches"][branch]["commits"]
        if target in commits:
            del commits[commits.index(target) + 1 :]
        self.state["branches"][branch]["head"] = target
        self._log("reset_branch", branch, {"target": target})

    def _log(self, action: str, target: str, detail: dict[str, Any]) -> None:
        self.state["call_log"].append(
            {"action": action, "target": target, "detail": copy.deepcopy(detail)}
        )

#!/usr/bin/env bash
set -euo pipefail

cat > release_train/reconcile.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from .api import LocalReleaseApi


@dataclass
class ReleaseReconciler:
    api: LocalReleaseApi
    plan: dict[str, Any]
    audit_path: str | Path

    def __post_init__(self) -> None:
        self.rows: list[dict[str, str]] = []
        self.branch = self.plan["release_branch"]
        self.tag = self.plan["release_tag"]

    @property
    def shas(self) -> list[str]:
        return [item["sha"] for item in self.plan["required_commits"]]

    @property
    def note_lines(self) -> list[str]:
        return [item["changelog"] for item in self.plan["required_commits"]]

    def append(self, action: str, target: str, detail: str) -> None:
        self.rows.append({"action": action, "target": target, "detail": detail})

    def write(self, rows: list[dict[str, str]] | None = None) -> None:
        chosen = self.rows if rows is None else rows
        Path(self.audit_path).write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in chosen)
        )

    def manifest(self, target: str) -> dict[str, Any]:
        return {
            "release_branch": self.plan["release_branch"],
            "source_branch": self.plan["source_branch"],
            "target": target,
            "required_commits": self.shas,
            "blocked_commits": list(self.plan.get("blocked_commits", [])),
            "required_checks": list(self.plan["required_checks"]),
            "promotion_rings": [ring["ring"] for ring in self.plan.get("promotion_rings", [])],
            "changelog_heading": self.plan["changelog_heading"],
        }

    def promotions(self, target: str) -> list[dict[str, Any]]:
        return [
            {
                "ring": ring["ring"],
                "target": target,
                "status": "ready",
                "approvers": list(ring["approvers"]),
                "note": ring["manifest_note"],
            }
            for ring in self.plan.get("promotion_rings", [])
        ]

    def check_passed(self, sha: str, check: str) -> bool:
        return self.api.state["status_checks"].get(sha, {}).get(check) == "passed"

    def notes_ready(self) -> bool:
        lines = self.api.state["changelog"].get(self.branch, [])
        return self.plan["changelog_heading"] in lines and all(line in lines for line in self.note_lines)

    def already_done(self) -> bool:
        branch_state = self.api.state["branches"][self.branch]
        target = branch_state["head"]
        if branch_state["head"] != self.shas[-1]:
            return False
        if any(sha not in branch_state["commits"] for sha in self.shas):
            return False
        if any(sha in branch_state["commits"] for sha in self.plan.get("blocked_commits", [])):
            return False
        if any(not self.check_passed(sha, check) for sha in self.shas for check in self.plan["required_checks"]):
            return False
        if any(
            not self.check_passed(target, check)
            for ring in self.plan.get("promotion_rings", [])
            for check in ring["required_checks"]
        ):
            return False
        if not self.notes_ready():
            return False
        if self.api.state["release_manifests"].get(self.tag) != self.manifest(target):
            return False
        if self.api.state["promotion_records"].get(self.tag) != self.promotions(target):
            return False
        return self.api.state["tags"].get(self.tag) == target

    def apply_missing_commits(self) -> None:
        available = set(self.api.state["branches"][self.plan["source_branch"]]["commits"])
        commits = self.api.state["branches"][self.branch]["commits"]
        blocked = set(self.plan.get("blocked_commits", []))
        for sha in self.shas:
            if sha in blocked:
                raise ValueError(f"blocked required commit: {sha}")
            if sha not in available:
                raise ValueError(f"missing required commit: {sha}")
            if sha not in commits:
                self.api.apply_commit(self.branch, sha)
                self.append("apply_commit", sha, f"applied to {self.branch}")
                commits = self.api.state["branches"][self.branch]["commits"]

    def run_commit_checks(self) -> None:
        for sha in self.shas:
            for check in self.plan["required_checks"]:
                if not self.check_passed(sha, check):
                    self.api.run_check(sha, check)
                    self.append("run_check", f"{sha}:{check}", "marked passed")

    def run_promotion_checks(self, target: str) -> None:
        for ring in self.plan.get("promotion_rings", []):
            for check in ring["required_checks"]:
                if not self.check_passed(target, check):
                    self.api.run_check(target, check)
                    self.append("run_check", f"{target}:{check}", "marked passed")

    def update_notes(self) -> None:
        if not self.notes_ready():
            self.api.update_changelog(self.branch, self.plan["changelog_heading"], self.note_lines)
            self.append("update_changelog", self.branch, "added missing release notes")

    def write_manifest_and_promotions(self, target: str) -> None:
        wanted_manifest = self.manifest(target)
        if self.api.state["release_manifests"].get(self.tag) != wanted_manifest:
            self.api.write_release_manifest(self.tag, wanted_manifest)
            self.append("write_manifest", self.tag, "wrote release manifest")
        records = self.api.state["promotion_records"].get(self.tag, [])
        for record in self.promotions(target):
            if record not in records:
                self.api.record_promotion(self.tag, record)
                self.append("record_promotion", f"{self.tag}:{record['ring']}", "recorded promotion readiness")
                records = self.api.state["promotion_records"].get(self.tag, [])

    def create_release_tag(self, target: str) -> None:
        if self.api.state["tags"].get(self.tag) != target:
            self.api.create_tag(self.tag, target)
            self.append("create_tag", self.tag, f"tagged {target}")

    def run(self) -> None:
        if self.already_done():
            self.write([{"action": "noop", "target": self.tag, "detail": "already reconciled"}])
            return
        self.apply_missing_commits()
        self.run_commit_checks()
        target = self.api.state["branches"][self.branch]["head"]
        self.run_promotion_checks(target)
        self.update_notes()
        self.write_manifest_and_promotions(target)
        self.create_release_tag(target)
        self.write(self.rows or [{"action": "noop", "target": self.tag, "detail": "already reconciled"}])


def reconcile_release(api: LocalReleaseApi, plan: dict[str, Any], audit_path: str | Path) -> None:
    ReleaseReconciler(api, plan, audit_path).run()
PY

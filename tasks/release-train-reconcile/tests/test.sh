#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


FORBIDDEN_ACTIONS = {"delete_branch", "delete_tag", "force_update_branch", "reset_branch"}


def run_release(
    root: Path, plan: dict[str, object], state: dict[str, object]
) -> tuple[dict[str, object], list[dict[str, str]]]:
    plan_path = root / "release_plan.json"
    state_path = root / "state.json"
    output_path = root / "output.json"
    audit_path = root / "audit.jsonl"
    plan_path.write_text(json.dumps(plan, indent=2))
    state_path.write_text(json.dumps(state, indent=2))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "release_train.cli",
            "--plan",
            str(plan_path),
            "--state",
            str(state_path),
            "--output-state",
            str(output_path),
            "--audit-log",
            str(audit_path),
        ],
        check=True,
    )
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()]
    return json.loads(output_path.read_text()), audit


def visible_plan() -> dict[str, object]:
    return json.loads(Path("/app/fixtures/release_plan.json").read_text())


def visible_state() -> dict[str, object]:
    return json.loads(Path("/app/fixtures/state.json").read_text())


def hidden_plan() -> dict[str, object]:
    return {
        "release_branch": "release/3.1",
        "source_branch": "main",
        "release_tag": "v3.1.0",
        "required_checks": ["unit", "security"],
        "required_commits": [
            {
                "sha": "h2",
                "title": "Harden token refresh",
                "changelog": "- Harden token refresh handling.",
            },
            {
                "sha": "h3",
                "title": "Backfill export audit",
                "changelog": "- Backfill export audit logging.",
            },
        ],
        "blocked_commits": ["h4"],
        "changelog_heading": "## v3.1.0 - 2026-07-05",
        "promotion_rings": [
            {
                "ring": "canary",
                "required_checks": ["deploy-canary"],
                "approvers": ["release-manager"],
                "manifest_note": "Canary ready after targeted deploy.",
            },
            {
                "ring": "production",
                "required_checks": ["prod-freeze", "pager-coverage"],
                "approvers": ["release-manager", "incident-commander"],
                "manifest_note": "Production ready with incident commander coverage.",
            },
        ],
    }


def hidden_state() -> dict[str, object]:
    return {
        "branches": {
            "main": {"head": "h4", "commits": ["h1", "h2", "h3", "h4"]},
            "release/3.1": {"head": "h2", "commits": ["h1", "h2"]},
            "release/3.0": {"head": "h1", "commits": ["h1"]},
        },
        "tags": {"v3.0.0": "h1"},
        "status_checks": {
            "h2": {"unit": "passed"},
            "h3": {
                "unit": "pending",
                "security": "failed",
                "deploy-canary": "passed",
                "prod-freeze": "pending",
            },
            "h4": {
                "unit": "passed",
                "security": "passed",
                "deploy-canary": "passed",
                "prod-freeze": "passed",
                "pager-coverage": "passed",
            },
        },
        "changelog": {
            "release/3.1": [
                "# Release notes",
                "## v3.1.0 - 2026-07-05",
                "- Harden token refresh handling.",
            ],
            "release/3.0": ["# Release notes"],
        },
        "release_manifests": {},
        "promotion_records": {},
        "call_log": [],
    }


def expected_manifest(plan: dict[str, object], target: str) -> dict[str, object]:
    return {
        "release_branch": plan["release_branch"],
        "source_branch": plan["source_branch"],
        "target": target,
        "required_commits": [commit["sha"] for commit in plan["required_commits"]],
        "blocked_commits": list(plan["blocked_commits"]),
        "required_checks": list(plan["required_checks"]),
        "promotion_rings": [ring["ring"] for ring in plan["promotion_rings"]],
        "changelog_heading": plan["changelog_heading"],
    }


def expected_promotions(plan: dict[str, object], target: str) -> list[dict[str, object]]:
    return [
        {
            "ring": ring["ring"],
            "target": target,
            "status": "ready",
            "approvers": list(ring["approvers"]),
            "note": ring["manifest_note"],
        }
        for ring in plan["promotion_rings"]
    ]


def assert_manifest_and_promotions(
    test: unittest.TestCase, output: dict[str, object], plan: dict[str, object], target: str
) -> None:
    tag = plan["release_tag"]
    test.assertEqual(output["release_manifests"][tag], expected_manifest(plan, target))
    test.assertEqual(output["promotion_records"][tag], expected_promotions(plan, target))


def action_positions(audit: list[dict[str, str]]) -> dict[str, list[int]]:
    positions: dict[str, list[int]] = {}
    for index, row in enumerate(audit):
        positions.setdefault(row["action"], []).append(index)
    return positions


def assert_ordering(test: unittest.TestCase, audit: list[dict[str, str]]) -> None:
    positions = action_positions(audit)
    if "apply_commit" in positions and "run_check" in positions:
        test.assertLess(max(positions["apply_commit"]), min(positions["run_check"]))
    if "run_check" in positions and "update_changelog" in positions:
        test.assertLess(max(positions["run_check"]), min(positions["update_changelog"]))
    if "update_changelog" in positions and "write_manifest" in positions:
        test.assertLess(max(positions["update_changelog"]), min(positions["write_manifest"]))
    if "write_manifest" in positions and "record_promotion" in positions:
        test.assertLess(max(positions["write_manifest"]), min(positions["record_promotion"]))
    if "record_promotion" in positions and "create_tag" in positions:
        test.assertLess(max(positions["record_promotion"]), min(positions["create_tag"]))


def assert_audit_schema(test: unittest.TestCase, audit: list[dict[str, str]]) -> None:
    allowed = {
        "apply_commit",
        "run_check",
        "update_changelog",
        "write_manifest",
        "record_promotion",
        "create_tag",
        "noop",
    }
    for row in audit:
        test.assertEqual(set(row), {"action", "target", "detail"})
        test.assertIn(row["action"], allowed)
        test.assertIsInstance(row["detail"], str)
        test.assertTrue(row["detail"])


class ReleaseTrainReconcileTests(unittest.TestCase):
    def test_visible_reconciles_release_train_in_required_order(self) -> None:
        plan = visible_plan()
        with tempfile.TemporaryDirectory() as tmp:
            output, audit = run_release(Path(tmp), plan, visible_state())

        release = output["branches"]["release/2.7"]
        self.assertEqual(release["commits"], ["c1", "c2", "c3", "c4", "c5"])
        self.assertEqual(release["head"], "c5")
        self.assertNotIn("c6", release["commits"])
        self.assertEqual(output["branches"]["release/2.6"]["commits"], ["c1", "c2"])

        for check in ["unit", "integration", "smoke"]:
            self.assertEqual(output["status_checks"]["c4"][check], "passed")
            self.assertEqual(output["status_checks"]["c5"][check], "passed")
        for check in ["deploy-canary", "smoke-canary", "prod-freeze", "pager-coverage"]:
            self.assertEqual(output["status_checks"]["c5"][check], "passed")

        changelog = output["changelog"]["release/2.7"]
        self.assertIn("## v2.7.0 - 2026-07-05", changelog)
        self.assertEqual(changelog.count("- Fix payout rounding drift."), 1)
        self.assertEqual(changelog.count("- Patch invoice export ordering."), 1)
        self.assertLess(changelog.index("- Fix payout rounding drift."), changelog.index("- Patch invoice export ordering."))
        assert_manifest_and_promotions(self, output, plan, "c5")
        self.assertEqual(output["tags"]["v2.7.0"], "c5")

        actions = [(row["action"], row["target"]) for row in audit]
        self.assertEqual(
            actions,
            [
                ("apply_commit", "c4"),
                ("apply_commit", "c5"),
                ("run_check", "c5:integration"),
                ("run_check", "c5:smoke"),
                ("run_check", "c5:deploy-canary"),
                ("run_check", "c5:smoke-canary"),
                ("run_check", "c5:prod-freeze"),
                ("run_check", "c5:pager-coverage"),
                ("update_changelog", "release/2.7"),
                ("write_manifest", "v2.7.0"),
                ("record_promotion", "v2.7.0:canary"),
                ("record_promotion", "v2.7.0:production"),
                ("create_tag", "v2.7.0"),
            ],
        )
        assert_ordering(self, audit)
        assert_audit_schema(self, audit)
        self.assertFalse(FORBIDDEN_ACTIONS.intersection(row["action"] for row in output["call_log"]))

    def test_hidden_handles_partial_prior_state_and_idempotent_noop(self) -> None:
        plan = hidden_plan()
        state = hidden_state()
        with tempfile.TemporaryDirectory() as tmp:
            output, audit = run_release(Path(tmp), plan, state)

        release = output["branches"]["release/3.1"]
        self.assertEqual(release["commits"], ["h1", "h2", "h3"])
        self.assertEqual(release["head"], "h3")
        self.assertNotIn("h4", release["commits"])
        self.assertEqual(output["tags"]["v3.1.0"], "h3")
        self.assertEqual(output["status_checks"]["h2"]["unit"], "passed")
        self.assertEqual(output["status_checks"]["h2"]["security"], "passed")
        self.assertEqual(output["status_checks"]["h3"]["unit"], "passed")
        self.assertEqual(output["status_checks"]["h3"]["security"], "passed")
        self.assertEqual(output["status_checks"]["h3"]["deploy-canary"], "passed")
        self.assertEqual(output["status_checks"]["h3"]["prod-freeze"], "passed")
        self.assertEqual(output["status_checks"]["h3"]["pager-coverage"], "passed")

        changelog = output["changelog"]["release/3.1"]
        self.assertEqual(changelog.count("- Harden token refresh handling."), 1)
        self.assertEqual(changelog.count("- Backfill export audit logging."), 1)
        self.assertLess(
            changelog.index("- Harden token refresh handling."),
            changelog.index("- Backfill export audit logging."),
        )
        assert_manifest_and_promotions(self, output, plan, "h3")

        actions = [(row["action"], row["target"]) for row in audit]
        self.assertEqual(
            actions,
            [
                ("apply_commit", "h3"),
                ("run_check", "h2:security"),
                ("run_check", "h3:unit"),
                ("run_check", "h3:security"),
                ("run_check", "h3:prod-freeze"),
                ("run_check", "h3:pager-coverage"),
                ("update_changelog", "release/3.1"),
                ("write_manifest", "v3.1.0"),
                ("record_promotion", "v3.1.0:canary"),
                ("record_promotion", "v3.1.0:production"),
                ("create_tag", "v3.1.0"),
            ],
        )
        assert_ordering(self, audit)
        assert_audit_schema(self, audit)
        self.assertFalse(FORBIDDEN_ACTIONS.intersection(row["action"] for row in output["call_log"]))

        replay_state = dict(output)
        replay_state["call_log"] = []
        with tempfile.TemporaryDirectory() as tmp:
            replay, replay_audit = run_release(Path(tmp), plan, replay_state)
        self.assertEqual(replay["branches"], replay_state["branches"])
        self.assertEqual(replay["tags"], replay_state["tags"])
        self.assertEqual(replay["status_checks"], replay_state["status_checks"])
        self.assertEqual(replay["changelog"], replay_state["changelog"])
        self.assertEqual(replay["release_manifests"], replay_state["release_manifests"])
        self.assertEqual(replay["promotion_records"], replay_state["promotion_records"])
        self.assertEqual(len(replay_audit), 1)
        self.assertEqual(replay_audit[0]["action"], "noop")
        self.assertEqual(replay_audit[0]["target"], "v3.1.0")
        self.assertIsInstance(replay_audit[0]["detail"], str)
        self.assertTrue(replay_audit[0]["detail"])

    def test_release_tag_is_not_created_before_checks_and_changelog(self) -> None:
        plan = hidden_plan()
        state = hidden_state()
        with tempfile.TemporaryDirectory() as tmp:
            output, audit = run_release(Path(tmp), plan, state)

        call_actions = [row["action"] for row in output["call_log"]]
        self.assertIn("create_tag", call_actions)
        tag_index = call_actions.index("create_tag")
        for index, row in enumerate(output["call_log"]):
            if row["action"] == "run_check":
                self.assertLess(index, tag_index)
            if row["action"] == "update_changelog":
                self.assertLess(index, tag_index)
            if row["action"] == "write_manifest":
                self.assertLess(index, tag_index)
            if row["action"] == "record_promotion":
                self.assertLess(index, tag_index)
        assert_ordering(self, audit)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseTrainReconcileTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"

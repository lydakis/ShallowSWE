#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


app = Path(os.environ.get("APP_DIR", "/app"))


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


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


def desired_gates(results: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    result_by_suite = {
        (str(result["project"]), str(result["commit"]), str(result["suite"])): result
        for result in results
    }
    gate_keys = sorted(
        {
            (str(result["project"]), str(environment), str(result["commit"]))
            for result in results
            for environment in result.get("environments", [])
        }
    )
    gates: list[dict[str, Any]] = []
    for project, environment, commit in gate_keys:
        blockers: list[str] = []
        required = rules.get("required_suites", {}).get(project, {}).get(environment, [])
        for suite in required:
            result = result_by_suite.get((project, commit, suite))
            if result is None:
                blockers.append(f"missing:{suite}")
                continue
            if result.get("failed"):
                blockers.append(f"failed:{suite}")
            if result.get("flaky") and result.get("blocking") is True:
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


def first_owner(results: list[dict[str, Any]], project: str, commit: str) -> str:
    for result in results:
        if str(result["project"]) == project and str(result["commit"]) == commit:
            return str(result.get("owner") or "unassigned")
    return "unassigned"


def channel(owner: str, rules: dict[str, Any]) -> str:
    return str(rules.get("owner_channels", {}).get(owner, rules.get("default_channel", "#builds")))


def desired_notifications(
    results: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    rules: dict[str, Any],
) -> list[dict[str, str]]:
    protected = set(rules.get("protected_branches", []))
    by_key: dict[str, dict[str, str]] = {}
    for result in results:
        if result.get("branch") in protected and result.get("blocking") is True and result.get("failed"):
            commit = str(result["commit"])
            project = str(result["project"])
            suite = str(result["suite"])
            owner = str(result.get("owner") or "unassigned")
            key = f"result:{commit}:{project}:{suite}:failure"
            by_key[key] = {
                "key": key,
                "channel": channel(owner, rules),
                "owner": owner,
                "kind": "result_failure",
                "summary": f"{project}/{suite} failed on protected branch {result['branch']} for {commit}",
            }
    for gate in gates:
        if gate["environment"] == "prod" and gate["state"] == "blocked":
            project = str(gate["project"])
            commit = str(gate["commit"])
            owner = first_owner(results, project, commit)
            key = f"gate:{project}:{gate['environment']}:{commit}:blocked"
            by_key[key] = {
                "key": key,
                "channel": channel(owner, rules),
                "owner": owner,
                "kind": "gate_blocked",
                "summary": f"{project} {gate['environment']} blocked for {commit}: {', '.join(gate['blockers'])}",
            }
    return [by_key[key] for key in sorted(by_key)]


def expected(root: Path) -> dict[str, Any]:
    results = read_json(root / "input" / "build_results.json", [])
    rules = read_json(root / "input" / "release_rules.json", {})
    api_state = root / "api_state"

    status_index = {
        (row["commit"], row["context"]): copy.deepcopy(row)
        for row in read_json(api_state / "statuses.json", [])
    }
    calls: list[str] = []
    status_updates = 0
    prefix = str(rules.get("context_prefix", "ci"))
    for result in results:
        target = desired_status(result, prefix)
        key = (target["commit"], target["context"])
        current = status_index.get(key)
        if current is None:
            status_index[key] = target
            calls.append(f"post_status {target['commit']} {target['context']} {target['state']}")
            status_updates += 1
        elif current.get("state") != target["state"] or current.get("body") != target["body"]:
            status_index[key] = target
            calls.append(f"update_status {target['commit']} {target['context']} {target['state']}")
            status_updates += 1

    gate_index = {
        (row["project"], row["environment"], row["commit"]): copy.deepcopy(row)
        for row in read_json(api_state / "deployment_gates.json", [])
    }
    target_gates = desired_gates(results, rules)
    gate_calls: list[str] = []
    for target in target_gates:
        key = (target["project"], target["environment"], target["commit"])
        current = gate_index.get(key)
        if current is None:
            gate_index[key] = target
            gate_calls.append(
                f"post_gate {target['project']} {target['environment']} {target['commit']} {target['state']}"
            )
        elif (
            current.get("state") != target["state"]
            or current.get("blockers") != target["blockers"]
            or current.get("updated_at") != target["updated_at"]
        ):
            gate_index[key] = target
            gate_calls.append(
                f"update_gate {target['project']} {target['environment']} {target['commit']} {target['state']}"
            )
    calls.extend(gate_calls)

    notification_index = {
        row["key"]: copy.deepcopy(row)
        for row in read_json(api_state / "notifications.json", [])
    }
    new_notifications: list[dict[str, str]] = []
    for notification in desired_notifications(results, target_gates, rules):
        if notification["key"] not in notification_index:
            notification_index[notification["key"]] = notification
            new_notifications.append(notification)
    calls.extend(f"notify {item['key']}" for item in sorted(new_notifications, key=lambda item: item["key"]))

    blocked = [gate for gate in target_gates if gate["state"] == "blocked"]
    return {
        "statuses": sorted(status_index.values(), key=lambda row: (row["commit"], row["context"])),
        "deployment_gates": sorted(
            gate_index.values(),
            key=lambda row: (row["project"], row["environment"], row["commit"]),
        ),
        "notifications": sorted(notification_index.values(), key=lambda row: row["key"]),
        "calls": calls,
        "summary": {
            "generated_at": rules["report_time"],
            "results_seen": len(results),
            "status_updates": status_updates,
            "gate_updates": len(gate_calls),
            "notifications_sent": len(new_notifications),
            "failed_results": sum(1 for result in results if result.get("failed")),
            "blocked_gates": len(blocked),
            "ready_gates": sum(1 for gate in target_gates if gate["state"] == "ready"),
            "projects_with_blocked_prod": sorted(
                {gate["project"] for gate in blocked if gate["environment"] == "prod"}
            ),
        },
    }


def copy_app(root: Path) -> None:
    (root / "scripts").mkdir(parents=True)
    (root / "input").mkdir()
    (root / "api_state").mkdir()
    shutil.copy2(app / "scripts" / "apply_task.py", root / "scripts" / "apply_task.py")


def run(root: Path) -> None:
    script = root / "scripts" / "apply_task.py"
    assert script.exists(), "missing scripts/apply_task.py"
    subprocess.run([sys.executable, str(script)], cwd=root, check=True)


def assert_outputs(testcase: unittest.TestCase, root: Path, expected_value: dict[str, Any]) -> None:
    testcase.assertEqual(read_json(root / "api_state" / "statuses.json", []), expected_value["statuses"])
    testcase.assertEqual(
        read_json(root / "api_state" / "deployment_gates.json", []),
        expected_value["deployment_gates"],
    )
    testcase.assertEqual(
        read_json(root / "api_state" / "notifications.json", []),
        expected_value["notifications"],
    )
    testcase.assertEqual((root / "api_state" / "calls.log").read_text().splitlines(), expected_value["calls"])
    testcase.assertEqual(read_json(root / "api_state" / "release_summary.json", {}), expected_value["summary"])

    for status in expected_value["statuses"]:
        testcase.assertEqual(set(status), {"commit", "context", "state", "body"})
    for gate in expected_value["deployment_gates"]:
        testcase.assertEqual(set(gate), {"project", "environment", "commit", "state", "blockers", "updated_at"})
        testcase.assertIn(gate["state"], {"blocked", "ready"})
    for notification in expected_value["notifications"]:
        testcase.assertEqual(set(notification), {"key", "channel", "owner", "kind", "summary"})


def visible_root(tmp: Path) -> Path:
    root = tmp / "app"
    copy_app(root)
    write_json(
        root / "input" / "build_results.json",
        [
            {
                "commit": "a1b2c3d",
                "project": "web",
                "suite": "unit",
                "branch": "main",
                "owner": "frontend",
                "passed": 120,
                "failed": [],
                "flaky": [],
                "blocking": True,
                "environments": ["staging", "prod"],
            },
            {
                "commit": "a1b2c3d",
                "project": "web",
                "suite": "e2e",
                "branch": "main",
                "owner": "frontend",
                "passed": 31,
                "failed": ["checkout.spec.ts", "coupon.spec.ts"],
                "flaky": [],
                "blocking": True,
                "environments": ["staging", "prod"],
            },
            {
                "commit": "d4e5f6a",
                "project": "api",
                "suite": "unit",
                "branch": "release/2026-08",
                "owner": "platform",
                "passed": 88,
                "failed": [],
                "flaky": ["retry_test.py"],
                "blocking": True,
                "environments": ["staging"],
            },
            {
                "commit": "d4e5f6a",
                "project": "api",
                "suite": "integration",
                "branch": "release/2026-08",
                "owner": "platform",
                "passed": 42,
                "failed": [],
                "flaky": [],
                "blocking": True,
                "environments": ["staging", "prod"],
            },
            {
                "commit": "f7a8b9c",
                "project": "worker",
                "suite": "lint",
                "branch": "feature/queue",
                "owner": "ops",
                "passed": 14,
                "failed": [],
                "flaky": [],
                "blocking": False,
                "environments": ["staging"],
            },
        ],
    )
    write_json(
        root / "input" / "release_rules.json",
        {
            "report_time": "2026-08-12T09:30:00Z",
            "context_prefix": "ci",
            "protected_branches": ["main", "release/2026-08"],
            "required_suites": {
                "web": {
                    "staging": ["unit", "e2e"],
                    "prod": ["unit", "e2e"],
                },
                "api": {
                    "staging": ["unit", "integration"],
                    "prod": ["unit", "integration", "security"],
                },
                "worker": {
                    "staging": ["lint"],
                },
            },
            "owner_channels": {
                "frontend": "#team-frontend",
                "platform": "#team-platform",
            },
            "default_channel": "#builds",
        },
    )
    write_json(
        root / "api_state" / "statuses.json",
        [
            {
                "commit": "a1b2c3d",
                "context": "ci/web/unit",
                "state": "success",
                "body": "web unit passed on a1b2c3d: 120 checks",
            },
            {
                "commit": "a1b2c3d",
                "context": "ci/web/e2e",
                "state": "success",
                "body": "web e2e passed on a1b2c3d: 31 checks",
            },
            {
                "commit": "d4e5f6a",
                "context": "ci/api/unit",
                "state": "success",
                "body": "api unit passed on d4e5f6a: 88 checks",
            },
            {
                "commit": "f7a8b9c",
                "context": "ci/worker/lint",
                "state": "success",
                "body": "worker lint passed on f7a8b9c: 14 checks",
            },
            {
                "commit": "z9z9z9z",
                "context": "ci/legacy/unit",
                "state": "success",
                "body": "legacy unit passed on z9z9z9z: 44 checks",
            },
        ],
    )
    write_json(
        root / "api_state" / "deployment_gates.json",
        [
            {
                "project": "web",
                "environment": "staging",
                "commit": "a1b2c3d",
                "state": "ready",
                "blockers": [],
                "updated_at": "2026-08-10T00:00:00Z",
            },
            {
                "project": "legacy",
                "environment": "prod",
                "commit": "z9z9z9z",
                "state": "ready",
                "blockers": [],
                "updated_at": "2026-08-01T00:00:00Z",
            },
        ],
    )
    write_json(
        root / "api_state" / "notifications.json",
        [
            {
                "key": "result:old:legacy:unit:failure",
                "channel": "#legacy",
                "owner": "legacy",
                "kind": "result_failure",
                "summary": "legacy/unit failed on protected branch main for old",
            }
        ],
    )
    (root / "api_state" / "calls.log").write_text("")
    return root


def hidden_root(tmp: Path) -> Path:
    root = tmp / "app"
    copy_app(root)
    write_json(
        root / "input" / "release_rules.json",
        {
            "report_time": "2026-09-02T18:45:00Z",
            "context_prefix": "checks",
            "protected_branches": ["main", "release/2026-09"],
            "required_suites": {
                "mobile": {
                    "staging": ["unit", "ui"],
                    "prod": ["unit", "ui", "security"],
                },
                "search": {
                    "prod": ["unit", "load"],
                },
                "docs": {
                    "preview": ["lint"],
                },
            },
            "owner_channels": {
                "client": "#client-app",
                "search": "#search",
            },
            "default_channel": "#release-alerts",
        },
    )
    write_json(
        root / "input" / "build_results.json",
        [
            {
                "commit": "m111",
                "project": "mobile",
                "suite": "unit",
                "branch": "main",
                "owner": "client",
                "passed": 61,
                "failed": [],
                "flaky": ["test_retry_login"],
                "blocking": True,
                "environments": ["staging", "prod"],
            },
            {
                "commit": "m111",
                "project": "mobile",
                "suite": "ui",
                "branch": "main",
                "owner": "client",
                "passed": 22,
                "failed": ["checkout_flow"],
                "flaky": [],
                "blocking": True,
                "environments": ["staging", "prod"],
            },
            {
                "commit": "s222",
                "project": "search",
                "suite": "unit",
                "branch": "release/2026-09",
                "owner": "search",
                "passed": 97,
                "failed": [],
                "flaky": [],
                "blocking": True,
                "environments": ["prod"],
            },
            {
                "commit": "s222",
                "project": "search",
                "suite": "load",
                "branch": "release/2026-09",
                "owner": "search",
                "passed": 11,
                "failed": [],
                "flaky": ["p95_latency"],
                "blocking": True,
                "environments": ["prod"],
            },
            {
                "commit": "d333",
                "project": "docs",
                "suite": "lint",
                "branch": "main",
                "owner": "docs",
                "passed": 8,
                "failed": ["broken_link"],
                "flaky": [],
                "blocking": True,
                "environments": ["preview"],
            },
        ],
    )
    write_json(
        root / "api_state" / "statuses.json",
        [
            {
                "commit": "m111",
                "context": "checks/mobile/unit",
                "state": "success",
                "body": "old unit body",
            },
            {
                "commit": "s222",
                "context": "checks/search/unit",
                "state": "success",
                "body": "search unit passed on s222: 97 checks",
            },
            {
                "commit": "keep",
                "context": "checks/legacy/unit",
                "state": "success",
                "body": "keep me",
            },
        ],
    )
    write_json(
        root / "api_state" / "deployment_gates.json",
        [
            {
                "project": "mobile",
                "environment": "staging",
                "commit": "m111",
                "state": "ready",
                "blockers": [],
                "updated_at": "2026-09-01T00:00:00Z",
            },
            {
                "project": "keep",
                "environment": "prod",
                "commit": "keep",
                "state": "ready",
                "blockers": [],
                "updated_at": "2026-09-01T00:00:00Z",
            },
        ],
    )
    write_json(
        root / "api_state" / "notifications.json",
        [
            {
                "key": "gate:search:prod:s222:blocked",
                "channel": "#search",
                "owner": "search",
                "kind": "gate_blocked",
                "summary": "search prod blocked for s222: flaky:load",
            },
        ],
    )
    (root / "api_state" / "calls.log").write_text("stale call\n")
    return root


class StatusFanoutReconcileTests(unittest.TestCase):
    def test_visible_fixture_reconciles_statuses_gates_notifications_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = visible_root(Path(tmp))
            expected_value = expected(root)
            run(root)
            assert_outputs(self, root, expected_value)
            self.assertIn("update_status a1b2c3d ci/web/e2e failure", expected_value["calls"])
            self.assertIn("post_gate api prod d4e5f6a blocked", expected_value["calls"])
            self.assertIn("notify gate:web:prod:a1b2c3d:blocked", expected_value["calls"])

    def test_hidden_fixture_handles_missing_flaky_unmapped_and_unrelated_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = hidden_root(Path(tmp))
            expected_value = expected(root)
            run(root)
            assert_outputs(self, root, expected_value)
            self.assertIn("flaky:unit", next(g for g in expected_value["deployment_gates"] if g["project"] == "mobile" and g["environment"] == "prod")["blockers"])
            self.assertIn("missing:security", next(g for g in expected_value["deployment_gates"] if g["project"] == "mobile" and g["environment"] == "prod")["blockers"])
            self.assertTrue(any(item["channel"] == "#release-alerts" for item in expected_value["notifications"]))
            self.assertTrue(any(row["commit"] == "keep" for row in expected_value["statuses"]))
            self.assertTrue(any(row["project"] == "keep" for row in expected_value["deployment_gates"]))

    def test_replay_is_idempotent_and_resets_change_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = hidden_root(Path(tmp))
            first_expected = expected(root)
            run(root)
            assert_outputs(self, root, first_expected)
            second_expected = expected(root)
            run(root)
            assert_outputs(self, root, second_expected)
            self.assertEqual((root / "api_state" / "calls.log").read_text(), "")
            self.assertEqual(read_json(root / "api_state" / "release_summary.json", {})["status_updates"], 0)
            self.assertEqual(read_json(root / "api_state" / "release_summary.json", {})["gate_updates"], 0)
            self.assertEqual(read_json(root / "api_state" / "release_summary.json", {})["notifications_sent"], 0)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(StatusFanoutReconcileTests)
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

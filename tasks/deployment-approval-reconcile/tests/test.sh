#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json
import subprocess
import sys
import tempfile
import unittest


def row(action: str, service: str, ring: str, detail: str) -> dict[str, str]:
    return {"action": action, "service": service, "ring": ring, "detail": detail}


def checks(plan: dict[str, Any]) -> dict[tuple[str, str, str, str], str]:
    return {
        (item["service"], item["target_version"], item["ring"], item["check"]): item["result"]
        for item in plan.get("checks", [])
    }


def approvals(plan: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (item["service"], item["target_version"], item["ring"])
        for item in plan.get("approvals", [])
        if item.get("approved") is True
    }


def frozen(plan: dict[str, Any], service: str, ring: str) -> bool:
    now = plan["now"]
    for window in plan.get("freeze_windows", []):
        if window["service"] == service and window["ring"] == ring and window["start"] <= now < window["end"]:
            return True
    return False


def history_has(service_state: dict[str, Any], record: dict[str, str]) -> bool:
    return record in service_state.get("history", [])


def expected(state: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    output = copy.deepcopy(state)
    output.setdefault("services", {})
    output.setdefault("call_log", [])
    audit: list[dict[str, str]] = []
    check_results = checks(plan)
    approved = approvals(plan)

    for deployment in plan.get("deployments", []):
        service = deployment["service"]
        target = deployment["target_version"]
        listed = [ring for ring in plan["ring_order"] if ring in deployment["rings"]]
        saw_row = False
        for index, ring in enumerate(listed):
            service_state = output["services"].setdefault(service, {"rings": {}, "history": []})
            current = service_state.setdefault("rings", {}).get(ring)
            if current == target:
                audit.append(row("already_current", service, ring, target))
                saw_row = True
                continue

            prior_missing = next((prior for prior in listed[:index] if service_state["rings"].get(prior) != target), None)
            reason: str | None = None
            if prior_missing is not None:
                reason = f"prior_ring_not_deployed:{prior_missing}"
            elif frozen(plan, service, ring):
                reason = "freeze_window"
            elif ring in deployment.get("approval_required_for", []) and (service, target, ring) not in approved:
                reason = "missing_approval"
            else:
                for check in deployment.get("required_checks", {}).get(ring, []):
                    result = check_results.get((service, target, ring, check))
                    if result is None:
                        reason = f"missing_check:{check}"
                        break
                    if result != "pass":
                        reason = f"failed_check:{check}"
                        break
            if reason is not None:
                record = {"action": "blocked", "service": service, "ring": ring, "reason": reason}
                if not history_has(service_state, record):
                    service_state.setdefault("history", []).append(record)
                    output["call_log"].append({"action": "blocked", "service": service, "ring": ring, "detail": {"reason": reason}})
                audit.append(row("blocked", service, ring, reason))
                saw_row = True
                break

            service_state["rings"][ring] = target
            record = {"action": "deploy", "service": service, "ring": ring, "version": target}
            if not history_has(service_state, record):
                service_state.setdefault("history", []).append(record)
                output["call_log"].append({"action": "deploy", "service": service, "ring": ring, "detail": {"version": target}})
            audit.append(row("deploy", service, ring, target))
            saw_row = True
        if not saw_row:
            audit.append(row("noop", service, "*", "no changes"))
    return output, audit


def run_cli(root: Path, state: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    state_path = root / "state.json"
    plan_path = root / "plan.json"
    output_path = root / "output.json"
    audit_path = root / "audit.jsonl"
    state_path.write_text(json.dumps(state, indent=2))
    plan_path.write_text(json.dumps(plan, indent=2))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "deploy_ops.cli",
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
    return json.loads(output_path.read_text()), [json.loads(line) for line in audit_path.read_text().splitlines()]


def visible_state() -> dict[str, Any]:
    return json.loads(Path("/app/fixtures/state.json").read_text())


def visible_plan() -> dict[str, Any]:
    return json.loads(Path("/app/fixtures/plan.json").read_text())


def hidden_state() -> dict[str, Any]:
    return {
        "services": {
            "search": {
                "rings": {"canary": "4.1.0", "internal": "4.0.0", "prod": "4.0.0"},
                "history": [{"action": "deploy", "service": "search", "ring": "canary", "version": "4.1.0"}],
            },
            "billing": {
                "rings": {"canary": "7.0.0", "internal": "7.0.0", "prod": "6.9.0"},
                "history": [],
            },
            "reports": {
                "rings": {"canary": "1.2.0", "internal": "1.2.0", "prod": "1.2.0"},
                "history": [],
            },
        },
        "call_log": [{"action": "deploy", "service": "legacy", "ring": "prod", "detail": {"version": "0.1.0"}}],
    }


def hidden_plan() -> dict[str, Any]:
    return {
        "now": "2026-08-11T03:15:00Z",
        "ring_order": ["canary", "internal", "prod"],
        "deployments": [
            {
                "service": "search",
                "target_version": "4.1.0",
                "rings": ["canary", "internal", "prod"],
                "required_checks": {
                    "canary": ["smoke"],
                    "internal": ["smoke", "error-rate"],
                    "prod": ["smoke"],
                },
                "approval_required_for": ["prod"],
            },
            {
                "service": "billing",
                "target_version": "7.1.0",
                "rings": ["prod"],
                "required_checks": {"prod": ["smoke", "payments"]},
                "approval_required_for": ["prod"],
            },
        ],
        "approvals": [
            {"service": "search", "target_version": "4.1.0", "ring": "prod", "approved": True},
            {"service": "billing", "target_version": "7.1.0", "ring": "prod", "approved": True},
        ],
        "checks": [
            {"service": "search", "target_version": "4.1.0", "ring": "canary", "check": "smoke", "result": "pass"},
            {"service": "search", "target_version": "4.1.0", "ring": "internal", "check": "smoke", "result": "pass"},
            {"service": "search", "target_version": "4.1.0", "ring": "internal", "check": "error-rate", "result": "fail"},
            {"service": "billing", "target_version": "7.1.0", "ring": "prod", "check": "smoke", "result": "pass"},
        ],
        "freeze_windows": [
            {"service": "billing", "ring": "prod", "start": "2026-08-11T03:00:00Z", "end": "2026-08-11T04:00:00Z"}
        ],
    }


class DeploymentApprovalReconcileTests(unittest.TestCase):
    def assert_run(self, state: dict[str, Any], plan: dict[str, Any]) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output, audit = run_cli(root, state, plan)
        expected_state, expected_audit = expected(state, plan)
        self.assertEqual(output, expected_state)
        self.assertEqual(audit, expected_audit)
        for item in audit:
            self.assertEqual(set(item), {"action", "service", "ring", "detail"})
            self.assertIn(item["action"], {"deploy", "already_current", "blocked", "noop"})
            self.assertTrue(item["detail"])

    def test_visible_respects_checks_approval_freeze_and_ordering(self) -> None:
        self.assert_run(visible_state(), visible_plan())

    def test_hidden_failed_check_freeze_priority_and_unrelated_preservation(self) -> None:
        self.assert_run(hidden_state(), hidden_plan())

    def test_replay_does_not_duplicate_history(self) -> None:
        state = visible_state()
        plan = visible_plan()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            once, _audit = run_cli(root, state, plan)
            twice, second_audit = run_cli(root, once, plan)
        expected_twice, expected_second = expected(once, plan)
        self.assertEqual(twice, expected_twice)
        self.assertEqual(second_audit, expected_second)
        for service in twice["services"].values():
            seen = set()
            for record in service.get("history", []):
                encoded = json.dumps(record, sort_keys=True)
                self.assertNotIn(encoded, seen)
                seen.add(encoded)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentApprovalReconcileTests)
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

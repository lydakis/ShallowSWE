#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any
from collections import Counter
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


def change_requests(plan: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (item["service"], item["target_version"], item["ring"]): item
        for item in plan.get("change_requests", [])
    }


def frozen(plan: dict[str, Any], service: str, ring: str) -> bool:
    now = plan["now"]
    for window in plan.get("freeze_windows", []):
        if window["service"] == service and window["ring"] == ring and window["start"] <= now < window["end"]:
            return True
    return False


def history_has(service_state: dict[str, Any], record: dict[str, str]) -> bool:
    return record in service_state.get("history", [])


def notify(output: dict[str, Any], plan: dict[str, Any], item: dict[str, str]) -> None:
    if item["action"] not in {"deploy", "blocked"}:
        return
    owner = plan.get("service_owners", {}).get(item["service"], "unassigned")
    key = f"{item['service']}:{item['ring']}:{item['action']}:{item['detail']}"
    notification = {
        "key": key,
        "service": item["service"],
        "ring": item["ring"],
        "owner": owner,
        "kind": item["action"],
        "detail": item["detail"],
    }
    notifications = output.setdefault("notifications", [])
    if not any(existing.get("key") == key for existing in notifications):
        notifications.append(notification)


def summary(plan: dict[str, Any], audit: list[dict[str, str]]) -> dict[str, Any]:
    counts = Counter(item["action"] for item in audit)
    blocked_services = sorted({item["service"] for item in audit if item["action"] == "blocked"})
    owners = plan.get("service_owners", {})
    return {
        "generated_at": plan["now"],
        "deployments_attempted": len(plan.get("deployments", [])),
        "deployed": counts["deploy"],
        "already_current": counts["already_current"],
        "blocked": counts["blocked"],
        "noop": counts["noop"],
        "changed_services": sorted({item["service"] for item in audit if item["action"] == "deploy"}),
        "blocked_services": blocked_services,
        "owners_to_page": sorted({owners.get(service, "unassigned") for service in blocked_services}),
    }


def expected(
    state: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    output = copy.deepcopy(state)
    output.setdefault("services", {})
    output.setdefault("call_log", [])
    output.setdefault("notifications", [])
    audit: list[dict[str, str]] = []
    check_results = checks(plan)
    approved = approvals(plan)
    requests = change_requests(plan)

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
            elif ring in deployment.get("change_request_required_for", []):
                request = requests.get((service, target, ring))
                if request is None:
                    reason = "missing_change_request"
                elif request.get("status") != "approved":
                    reason = f"rejected_change_request:{request['request_id']}"
            if reason is None:
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
                item = row("blocked", service, ring, reason)
                audit.append(item)
                notify(output, plan, item)
                saw_row = True
                break

            service_state["rings"][ring] = target
            record = {"action": "deploy", "service": service, "ring": ring, "version": target}
            if not history_has(service_state, record):
                service_state.setdefault("history", []).append(record)
                output["call_log"].append({"action": "deploy", "service": service, "ring": ring, "detail": {"version": target}})
            item = row("deploy", service, ring, target)
            audit.append(item)
            notify(output, plan, item)
            saw_row = True
        if not saw_row:
            audit.append(row("noop", service, "*", "no changes"))
    return output, audit, summary(plan, audit)


def run_cli(
    root: Path,
    state: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    state_path = root / "state.json"
    plan_path = root / "plan.json"
    output_path = root / "output.json"
    audit_path = root / "audit.jsonl"
    summary_path = root / "summary.json"
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
            "--summary-report",
            str(summary_path),
        ],
        check=True,
    )
    return (
        json.loads(output_path.read_text()),
        [json.loads(line) for line in audit_path.read_text().splitlines()],
        json.loads(summary_path.read_text()),
    )


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
        "notifications": [
            {
                "key": "legacy:prod:deploy:0.1.0",
                "service": "legacy",
                "ring": "prod",
                "owner": "legacy-team",
                "kind": "deploy",
                "detail": "0.1.0",
            }
        ],
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
                "change_request_required_for": ["prod"],
            },
            {
                "service": "reports",
                "target_version": "1.3.0",
                "rings": ["prod"],
                "required_checks": {"prod": ["smoke"]},
                "approval_required_for": ["prod"],
                "change_request_required_for": ["prod"],
            },
        ],
        "service_owners": {
            "search": "team-search",
            "billing": "team-billing",
            "reports": "team-reports",
        },
        "approvals": [
            {"service": "search", "target_version": "4.1.0", "ring": "prod", "approved": True},
            {"service": "billing", "target_version": "7.1.0", "ring": "prod", "approved": True},
            {"service": "reports", "target_version": "1.3.0", "ring": "prod", "approved": True},
        ],
        "change_requests": [
            {"request_id": "CR-SEARCH", "service": "search", "target_version": "4.1.0", "ring": "prod", "status": "approved"},
            {"request_id": "CR-BILLING", "service": "billing", "target_version": "7.1.0", "ring": "prod", "status": "approved"},
            {"request_id": "CR-REPORTS", "service": "reports", "target_version": "1.3.0", "ring": "prod", "status": "rejected"},
        ],
        "checks": [
            {"service": "search", "target_version": "4.1.0", "ring": "canary", "check": "smoke", "result": "pass"},
            {"service": "search", "target_version": "4.1.0", "ring": "internal", "check": "smoke", "result": "pass"},
            {"service": "search", "target_version": "4.1.0", "ring": "internal", "check": "error-rate", "result": "fail"},
            {"service": "billing", "target_version": "7.1.0", "ring": "prod", "check": "smoke", "result": "pass"},
            {"service": "reports", "target_version": "1.3.0", "ring": "prod", "check": "smoke", "result": "pass"},
        ],
        "freeze_windows": [
            {"service": "billing", "ring": "prod", "start": "2026-08-11T03:00:00Z", "end": "2026-08-11T04:00:00Z"}
        ],
    }


class DeploymentApprovalReconcileTests(unittest.TestCase):
    def assert_run(self, state: dict[str, Any], plan: dict[str, Any]) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output, audit, actual_summary = run_cli(root, state, plan)
        expected_state, expected_audit, expected_summary = expected(state, plan)
        self.assertEqual(output, expected_state)
        self.assertEqual(audit, expected_audit)
        self.assertEqual(actual_summary, expected_summary)
        for item in audit:
            self.assertEqual(set(item), {"action", "service", "ring", "detail"})
            self.assertIn(item["action"], {"deploy", "already_current", "blocked", "noop"})
            self.assertTrue(item["detail"])
        for item in output["notifications"]:
            self.assertEqual(set(item), {"key", "service", "ring", "owner", "kind", "detail"})

    def test_visible_respects_checks_approval_freeze_and_ordering(self) -> None:
        self.assert_run(visible_state(), visible_plan())

    def test_hidden_failed_check_freeze_priority_and_unrelated_preservation(self) -> None:
        self.assert_run(hidden_state(), hidden_plan())

    def test_replay_does_not_duplicate_history(self) -> None:
        state = visible_state()
        plan = visible_plan()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            once, _audit, _summary = run_cli(root, state, plan)
            twice, second_audit, second_summary = run_cli(root, once, plan)
        expected_twice, expected_second, expected_summary = expected(once, plan)
        self.assertEqual(twice, expected_twice)
        self.assertEqual(second_audit, expected_second)
        self.assertEqual(second_summary, expected_summary)
        for service in twice["services"].values():
            seen = set()
            for record in service.get("history", []):
                encoded = json.dumps(record, sort_keys=True)
                self.assertNotIn(encoded, seen)
                seen.add(encoded)
        notification_keys = [item["key"] for item in twice["notifications"]]
        self.assertEqual(len(notification_keys), len(set(notification_keys)))


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

#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


APP = Path(os.environ.get("APP_DIR", "/app"))
OUTPUT_FILES = {"migration_readiness.json", "team_rollup.csv", "migration_board.md", "summary.json"}
LEGACY_TOKENS = [
    "LegacyPaymentClient",
    "legacy_charge(",
    "legacy_refund(",
    "verify_webhook_legacy(",
    "post_legacy_ledger(",
]
BLOCKER_ACTIONS = {
    "legacy_api_usage": "remove legacy payment API calls",
    "ci_failed": "fix failing migration CI",
    "contract_test_failed": "repair contract fixtures",
    "open_incident": "resolve active incident",
    "migration_flag_disabled": "enable payments_sdk_v4 flag",
    "frozen_cutover": "move cutover outside freeze window",
    "expired_exception": "renew or close expired exception",
    "security_advisory": "upgrade payments-sdk before migration",
}
BLOCKED_BLOCKERS = {
    "ci_failed",
    "contract_test_failed",
    "open_incident",
    "frozen_cutover",
    "expired_exception",
    "security_advisory",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def seed_repo(root: Path, *, variant: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if variant == "hidden-a":
        services = [
            {"service_id": "auth", "name": "Auth", "team": "identity", "tier": 1, "runtime": "go"},
            {"service_id": "invoicing", "name": "Invoicing", "team": "finance", "tier": 1, "runtime": "python"},
            {"service_id": "search", "name": "Search", "team": "growth", "tier": 3, "runtime": "typescript"},
            {"service_id": "payouts", "name": "Payouts", "team": "finance", "tier": 2, "runtime": "python"},
        ]
        owners = [
            {"team": "finance", "manager": "Fia Moss", "slack": "#finance", "email": "finance@example.com"},
            {"team": "growth", "manager": "Gia Nunez", "slack": "#growth", "email": "growth@example.com"},
            {"team": "identity", "manager": "Ian Cho", "slack": "#identity", "email": "identity@example.com"},
        ]
        packages = [
            {"service_id": "auth", "package": "payments-sdk", "current_version": "3.2.1", "target_version": "4.3.0", "scope": "direct", "critical": "true"},
            {"service_id": "invoicing", "package": "payments-sdk", "current_version": "4.1.0", "target_version": "4.3.0", "scope": "direct", "critical": "true"},
            {"service_id": "search", "package": "payments-sdk", "current_version": "4.3.0", "target_version": "4.3.0", "scope": "transitive", "critical": "false"},
            {"service_id": "payouts", "package": "payments-sdk", "current_version": "3.9.9", "target_version": "4.3.0", "scope": "direct", "critical": "true"},
        ]
        configs = {
            "auth": {"feature_flags": [], "deployment_strategy": "ring", "allow_legacy_webhooks": True},
            "invoicing": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "ring", "allow_legacy_webhooks": False},
            "search": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "ring", "allow_legacy_webhooks": False},
            "payouts": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "manual", "allow_legacy_webhooks": False},
        }
        logs = {
            "auth": "STATUS=pass\n",
            "invoicing": "STATUS=fail\nLEGACY_CONTRACT_TEST_FAILED invoice-contract\n",
            "search": "STATUS=pass\n",
            "payouts": "STATUS=pass\n",
        }
        incidents = [
            {"service_id": "auth", "date": "2026-09-01", "severity": "P2", "status": "open"},
            {"service_id": "invoicing", "date": "2026-09-03", "severity": "P0", "status": "open"},
            {"service_id": "payouts", "date": "2026-09-02", "severity": "P1", "status": "resolved"},
        ]
        exceptions = [
            {"service_id": "auth", "expires_on": "2026-09-20", "reason": "merchant callback lag", "approver": "cto"},
            {"service_id": "payouts", "expires_on": "2026-08-30", "reason": "batch partner", "approver": "vp-finance"},
        ]
        waves = {
            "report_date": "2026-09-05",
            "waves": [
                {"service_id": "auth", "wave": "identity-wave", "freeze_start": "2026-09-10", "freeze_end": "2026-09-12", "cutover_deadline": "2026-09-30"},
                {"service_id": "invoicing", "wave": "finance-wave", "freeze_start": "2026-09-01", "freeze_end": "2026-09-04", "cutover_deadline": "2026-09-18"},
                {"service_id": "search", "wave": "growth-wave", "freeze_start": "2026-09-15", "freeze_end": "2026-09-16", "cutover_deadline": "2026-10-01"},
                {"service_id": "payouts", "wave": "finance-wave", "freeze_start": "2026-09-04", "freeze_end": "2026-09-07", "cutover_deadline": "2026-09-18"},
            ],
        }
        code = {
            "auth": "func handle() { verify_webhook_legacy(payload); legacy_refund(order) }\n",
            "invoicing": "from payments import PaymentClient\n",
            "search": "export function noop() { return true }\n",
            "payouts": "from payments import LegacyPaymentClient\nLegacyPaymentClient().legacy_charge(invoice)\n",
        }
        advisory_version = "3.5.0"
    else:
        services = [
            {"service_id": "orders", "name": "Orders", "team": "commerce", "tier": 1, "runtime": "python"},
            {"service_id": "analytics", "name": "Analytics", "team": "data", "tier": 2, "runtime": "python"},
            {"service_id": "email", "name": "Email", "team": "growth", "tier": 3, "runtime": "typescript"},
        ]
        owners = [
            {"team": "commerce", "manager": "Cam Wu", "slack": "#commerce", "email": "commerce@example.com"},
            {"team": "data", "manager": "Dee Okafor", "slack": "#data", "email": "data@example.com"},
            {"team": "growth", "manager": "Greta Li", "slack": "#growth", "email": "growth@example.com"},
        ]
        packages = [
            {"service_id": "orders", "package": "payments-sdk", "current_version": "4.0.1", "target_version": "4.4.0", "scope": "direct", "critical": "true"},
            {"service_id": "analytics", "package": "payments-sdk", "current_version": "4.4.0", "target_version": "4.4.0", "scope": "transitive", "critical": "false"},
            {"service_id": "email", "package": "payments-sdk", "current_version": "3.1.0", "target_version": "4.4.0", "scope": "direct", "critical": "true"},
        ]
        configs = {
            "orders": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "ring", "allow_legacy_webhooks": False},
            "analytics": {"feature_flags": ["payments_sdk_v4"], "deployment_strategy": "manual", "allow_legacy_webhooks": False},
            "email": {"feature_flags": [], "deployment_strategy": "ring", "allow_legacy_webhooks": True},
        }
        logs = {
            "orders": "STATUS=pass\n",
            "analytics": "STATUS=pass\n",
            "email": "STATUS=pass\n",
        }
        incidents = [
            {"service_id": "orders", "date": "2026-11-02", "severity": "P1", "status": "resolved"},
            {"service_id": "email", "date": "2026-11-03", "severity": "P2", "status": "open"},
        ]
        exceptions = [
            {"service_id": "email", "expires_on": "2026-11-20", "reason": "esp migration", "approver": "vp-growth"},
        ]
        waves = {
            "report_date": "2026-11-05",
            "waves": [
                {"service_id": "orders", "wave": "commerce-wave", "freeze_start": "2026-11-07", "freeze_end": "2026-11-08", "cutover_deadline": "2026-11-18"},
                {"service_id": "analytics", "wave": "data-wave", "freeze_start": "2026-11-01", "freeze_end": "2026-11-02", "cutover_deadline": "2026-11-28"},
                {"service_id": "email", "wave": "growth-wave", "freeze_start": "2026-11-10", "freeze_end": "2026-11-12", "cutover_deadline": "2026-11-25"},
            ],
        }
        code = {
            "orders": "from payments import PaymentClient\n",
            "analytics": "from warehouse import run\n",
            "email": "verify_webhook_legacy(payload)\npost_legacy_ledger(row)\n",
        }
        advisory_version = "3.2.0"

    write_json(root / "catalog/services.json", services)
    write_csv(root / "owners/teams.csv", owners, ["team", "manager", "slack", "email"])
    write_csv(root / "dependencies/packages.csv", packages, ["service_id", "package", "current_version", "target_version", "scope", "critical"])
    for service_id, config in configs.items():
        write_json(root / f"configs/{service_id}.json", config)
    for service_id, log in logs.items():
        write(root / f"ci/{service_id}.log", log)
    write_csv(root / "incidents/incidents.csv", incidents, ["service_id", "date", "severity", "status"])
    write_csv(root / "migration/exceptions.csv", exceptions, ["service_id", "expires_on", "reason", "approver"])
    write_json(root / "migration/waves.json", waves)
    write(
        root / "advisories/payments-sdk.md",
        f"""---
package: payments-sdk
affected_below: {advisory_version}
severity: critical
action: upgrade before migration
---
""",
    )
    for service_id, source in code.items():
        suffix = "handler.ts" if "export " in source or service_id == "email" else "payment_flow.py"
        write(root / f"repos/{service_id}/src/{suffix}", source)
        for index in range(8):
            write(root / f"repos/{service_id}/src/noise_{index}.py", f"MARKER = '{service_id}-{index}'\n")
    return root


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def parse_advisory(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    data: dict[str, str] = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()
    return data


def legacy_count(root: Path, service_id: str) -> int:
    count = 0
    service_root = root / "repos" / service_id
    for path in service_root.rglob("*"):
        if path.suffix not in {".py", ".js", ".ts", ".go"}:
            continue
        text = path.read_text()
        count += sum(text.count(token) for token in LEGACY_TOKENS)
    return count


def expected(root: Path) -> dict[str, object]:
    services = json.loads((root / "catalog/services.json").read_text())
    owners = {row["team"]: row for row in read_csv(root / "owners/teams.csv")}
    packages = {
        row["service_id"]: row
        for row in read_csv(root / "dependencies/packages.csv")
        if row["package"] == "payments-sdk"
    }
    incidents = read_csv(root / "incidents/incidents.csv")
    exceptions = read_csv(root / "migration/exceptions.csv")
    waves_doc = json.loads((root / "migration/waves.json").read_text())
    report_date = waves_doc["report_date"]
    waves = {row["service_id"]: row for row in waves_doc["waves"]}
    advisory = parse_advisory(next((root / "advisories").glob("*.md")))

    exception_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in exceptions:
        exception_rows[row["service_id"]].append(row)

    open_incidents = Counter(
        row["service_id"]
        for row in incidents
        if row["status"] == "open" and row["severity"] in {"P0", "P1"}
    )

    rows = []
    for service in sorted(services, key=lambda row: row["service_id"]):
        service_id = service["service_id"]
        package = packages[service_id]
        config = json.loads((root / "configs" / f"{service_id}.json").read_text())
        log = (root / "ci" / f"{service_id}.log").read_text()
        wave = waves[service_id]
        count = legacy_count(root, service_id)
        ci_status = "fail" if "STATUS=fail" in log else "pass"
        active_exception = any(row["expires_on"] >= report_date for row in exception_rows[service_id])
        has_exception = bool(exception_rows[service_id])
        blockers = []
        if count > 0:
            blockers.append("legacy_api_usage")
        if ci_status == "fail":
            blockers.append("ci_failed")
        if "LEGACY_CONTRACT_TEST_FAILED" in log:
            blockers.append("contract_test_failed")
        if open_incidents[service_id] > 0:
            blockers.append("open_incident")
        if "payments_sdk_v4" not in config.get("feature_flags", []):
            blockers.append("migration_flag_disabled")
        if wave["freeze_start"] <= report_date <= wave["freeze_end"]:
            blockers.append("frozen_cutover")
        if has_exception and not active_exception and blockers:
            blockers.append("expired_exception")
        if (
            advisory["package"] == "payments-sdk"
            and advisory["severity"] == "critical"
            and version_tuple(package["current_version"]) < version_tuple(advisory["affected_below"])
        ):
            blockers.append("security_advisory")

        if any(blocker in BLOCKED_BLOCKERS for blocker in blockers):
            readiness = "blocked"
        elif active_exception and set(blockers).issubset({"legacy_api_usage", "migration_flag_disabled"}):
            readiness = "exception"
        elif blockers:
            readiness = "needs_work"
        else:
            readiness = "ready"

        rows.append(
            {
                "service_id": service_id,
                "name": service["name"],
                "team": service["team"],
                "tier": int(service["tier"]),
                "runtime": service["runtime"],
                "current_version": package["current_version"],
                "target_version": package["target_version"],
                "wave": wave["wave"],
                "cutover_deadline": wave["cutover_deadline"],
                "readiness": readiness,
                "blockers": blockers,
                "actions": [BLOCKER_ACTIONS[blocker] for blocker in blockers],
                "legacy_api_count": count,
                "ci_status": ci_status,
                "open_incidents": open_incidents[service_id],
                "exception_active": active_exception,
            }
        )

    by_team: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_team[str(row["team"])].append(row)
    team_rows = []
    for team in sorted(owners):
        owned = sorted(by_team.get(team, []), key=lambda row: str(row["service_id"]))
        team_rows.append(
            {
                "team": team,
                "manager": owners[team]["manager"],
                "slack": owners[team]["slack"],
                "email": owners[team]["email"],
                "services": ";".join(str(row["service_id"]) for row in owned),
                "ready": str(sum(row["readiness"] == "ready" for row in owned)),
                "needs_work": str(sum(row["readiness"] == "needs_work" for row in owned)),
                "blocked": str(sum(row["readiness"] == "blocked" for row in owned)),
                "exceptions": str(sum(row["readiness"] == "exception" for row in owned)),
                "legacy_api_count": str(sum(int(row["legacy_api_count"]) for row in owned)),
                "open_incidents": str(sum(int(row["open_incidents"]) for row in owned)),
                "highest_tier": str(min((int(row["tier"]) for row in owned), default=0) or ""),
            }
        )

    board_lines = ["# SDK Migration Board", ""]
    for title, status in [
        ("Blocked", "blocked"),
        ("Needs Work", "needs_work"),
        ("Ready", "ready"),
        ("Exceptions", "exception"),
    ]:
        board_lines.append(f"## {title}")
        status_rows = [row for row in rows if row["readiness"] == status]
        if not status_rows:
            board_lines.append("- none")
        else:
            for row in sorted(status_rows, key=lambda item: str(item["service_id"])):
                blockers = ";".join(row["blockers"]) if row["blockers"] else "none"
                action = row["actions"][0] if row["actions"] else "schedule cutover"
                board_lines.append(
                    f"- {row['service_id']} [{row['team']}] blockers={blockers} action={action}"
                )
        board_lines.append("")
    board = "\n".join(board_lines).rstrip() + "\n"

    summary = {
        "services": len(rows),
        "ready": sum(row["readiness"] == "ready" for row in rows),
        "needs_work": sum(row["readiness"] == "needs_work" for row in rows),
        "blocked": sum(row["readiness"] == "blocked" for row in rows),
        "exceptions": sum(row["readiness"] == "exception" for row in rows),
        "legacy_api_count": sum(int(row["legacy_api_count"]) for row in rows),
        "open_incidents": sum(int(row["open_incidents"]) for row in rows),
        "teams": len(owners),
        "waves": len({wave["wave"] for wave in waves.values()}),
    }
    return {
        "migration_readiness": {"services": rows},
        "team_rollup": team_rows,
        "migration_board": board,
        "summary": summary,
    }


def run_builder(root: Path) -> None:
    script = APP / "scripts" / "build_migration_readiness.py"
    if not script.exists():
        raise AssertionError("scripts/build_migration_readiness.py is missing")
    output = root / "output"
    if output.exists():
        shutil.rmtree(output)
    subprocess.run(
        [sys.executable, str(script), "--root", str(root), "--output", str(output)],
        check=True,
        cwd=APP,
    )


def assert_outputs(root: Path) -> None:
    run_builder(root)
    output = root / "output"
    actual_files = {path.name for path in output.iterdir() if path.is_file()}
    assert actual_files == OUTPUT_FILES, actual_files
    exp = expected(root)
    assert json.loads((output / "migration_readiness.json").read_text()) == exp["migration_readiness"]
    assert json.loads((output / "summary.json").read_text()) == exp["summary"]
    assert read_csv(output / "team_rollup.csv") == exp["team_rollup"]
    assert (output / "migration_board.md").read_text() == exp["migration_board"]


def main() -> int:
    try:
        assert_outputs(APP)
        with tempfile.TemporaryDirectory() as tmp:
            assert_outputs(seed_repo(Path(tmp) / "hidden-a", variant="hidden-a"))
        with tempfile.TemporaryDirectory() as tmp:
            assert_outputs(seed_repo(Path(tmp) / "hidden-b", variant="hidden-b"))
    except Exception as exc:
        print(f"VERIFIER_FAILED: {exc}", file=sys.stderr)
        (Path(os.environ.get("LOG_DIR", "/logs/verifier")) / "reward.txt").write_text("0")
        raise
    (Path(os.environ.get("LOG_DIR", "/logs/verifier")) / "reward.txt").write_text("1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

status=$?
if [[ $status -ne 0 ]]; then
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

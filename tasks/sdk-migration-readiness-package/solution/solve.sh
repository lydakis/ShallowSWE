#!/usr/bin/env bash
set -euo pipefail

mkdir -p scripts

cat > scripts/build_migration_readiness.py <<'PY'
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import csv
import json


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
TEAM_COLUMNS = [
    "team",
    "manager",
    "slack",
    "email",
    "services",
    "ready",
    "needs_work",
    "blocked",
    "exceptions",
    "legacy_api_count",
    "open_incidents",
    "highest_tier",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "---":
        return {}
    end = lines.index("---", 1)
    data: dict[str, str] = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()
    return data


def legacy_api_count(root: Path, service_id: str) -> int:
    total = 0
    service_root = root / "repos" / service_id
    for path in service_root.rglob("*"):
        if path.suffix not in {".py", ".js", ".ts", ".go"}:
            continue
        text = path.read_text()
        total += sum(text.count(token) for token in LEGACY_TOKENS)
    return total


def service_rows(root: Path) -> tuple[list[dict[str, object]], dict[str, dict[str, str]], dict[str, str]]:
    services = json.loads((root / "catalog" / "services.json").read_text())
    owners = {row["team"]: row for row in read_csv(root / "owners" / "teams.csv")}
    packages = {
        row["service_id"]: row
        for row in read_csv(root / "dependencies" / "packages.csv")
        if row["package"] == "payments-sdk"
    }
    incidents = read_csv(root / "incidents" / "incidents.csv")
    exceptions = read_csv(root / "migration" / "exceptions.csv")
    waves_doc = json.loads((root / "migration" / "waves.json").read_text())
    report_date = str(waves_doc["report_date"])
    waves = {row["service_id"]: row for row in waves_doc["waves"]}
    advisory = parse_frontmatter(next((root / "advisories").glob("*.md")))

    open_incidents = Counter(
        row["service_id"]
        for row in incidents
        if row["status"] == "open" and row["severity"] in {"P0", "P1"}
    )
    exceptions_by_service: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in exceptions:
        exceptions_by_service[row["service_id"]].append(row)

    rows: list[dict[str, object]] = []
    for service in sorted(services, key=lambda row: row["service_id"]):
        service_id = str(service["service_id"])
        package = packages[service_id]
        config = json.loads((root / "configs" / f"{service_id}.json").read_text())
        log = (root / "ci" / f"{service_id}.log").read_text()
        wave = waves[service_id]
        count = legacy_api_count(root, service_id)
        ci_status = "fail" if "STATUS=fail" in log else "pass"
        service_exceptions = exceptions_by_service[service_id]
        exception_active = any(row["expires_on"] >= report_date for row in service_exceptions)

        blockers: list[str] = []
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
        if str(wave["freeze_start"]) <= report_date <= str(wave["freeze_end"]):
            blockers.append("frozen_cutover")
        if service_exceptions and not exception_active and blockers:
            blockers.append("expired_exception")
        if (
            advisory.get("package") == "payments-sdk"
            and advisory.get("severity") == "critical"
            and version_tuple(package["current_version"]) < version_tuple(advisory["affected_below"])
        ):
            blockers.append("security_advisory")

        if any(blocker in BLOCKED_BLOCKERS for blocker in blockers):
            readiness = "blocked"
        elif exception_active and set(blockers).issubset({"legacy_api_usage", "migration_flag_disabled"}):
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
                "exception_active": exception_active,
            }
        )
    return rows, owners, {row["service_id"]: row["wave"] for row in waves_doc["waves"]}


def team_rollup(rows: list[dict[str, object]], owners: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    by_team: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_team[str(row["team"])].append(row)

    output = []
    for team in sorted(owners):
        owned = sorted(by_team.get(team, []), key=lambda row: str(row["service_id"]))
        tiers = [int(row["tier"]) for row in owned]
        output.append(
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
                "highest_tier": str(min(tiers)) if tiers else "",
            }
        )
    return output


def board(rows: list[dict[str, object]]) -> str:
    lines = ["# SDK Migration Board", ""]
    for title, status in [
        ("Blocked", "blocked"),
        ("Needs Work", "needs_work"),
        ("Ready", "ready"),
        ("Exceptions", "exception"),
    ]:
        lines.append(f"## {title}")
        section_rows = [row for row in rows if row["readiness"] == status]
        if not section_rows:
            lines.append("- none")
        else:
            for row in sorted(section_rows, key=lambda item: str(item["service_id"])):
                blockers = ";".join(row["blockers"]) if row["blockers"] else "none"
                action = row["actions"][0] if row["actions"] else "schedule cutover"
                lines.append(f"- {row['service_id']} [{row['team']}] blockers={blockers} action={action}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def summary(rows: list[dict[str, object]], owners: dict[str, dict[str, str]], wave_by_service: dict[str, str]) -> dict[str, int]:
    return {
        "services": len(rows),
        "ready": sum(row["readiness"] == "ready" for row in rows),
        "needs_work": sum(row["readiness"] == "needs_work" for row in rows),
        "blocked": sum(row["readiness"] == "blocked" for row in rows),
        "exceptions": sum(row["readiness"] == "exception" for row in rows),
        "legacy_api_count": sum(int(row["legacy_api_count"]) for row in rows),
        "open_incidents": sum(int(row["open_incidents"]) for row in rows),
        "teams": len(owners),
        "waves": len(set(wave_by_service.values())),
    }


def write_outputs(root: Path, output: Path) -> None:
    rows, owners, wave_by_service = service_rows(root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "migration_readiness.json").write_text(
        json.dumps({"services": rows}, indent=2, sort_keys=True) + "\n"
    )
    with (output / "team_rollup.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEAM_COLUMNS)
        writer.writeheader()
        writer.writerows(team_rollup(rows, owners))
    (output / "migration_board.md").write_text(board(rows))
    (output / "summary.json").write_text(
        json.dumps(summary(rows, owners, wave_by_service), indent=2, sort_keys=True) + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    root = Path(args.root)
    output = Path(args.output) if args.output else root / "output"
    write_outputs(root, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

python scripts/build_migration_readiness.py

#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

python3 - <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest


DASHBOARD_FIELDS = {
    "name",
    "owner",
    "plan",
    "risk_score",
    "risk_band",
    "open_ticket_count",
    "open_incident_count",
    "days_until_renewal",
    "arr",
    "contract_status",
    "engagement_gap",
    "open_playbooks",
    "overdue_playbooks",
    "next_playbook_due",
    "recommended_action",
}

ACTIONS_FIELDS = {
    "account",
    "owner",
    "risk_band",
    "recommended_action",
    "next_playbook_due",
    "overdue_playbooks",
    "open_playbooks",
    "arr",
    "engagement_gap",
}

OWNER_FIELDS = {
    "owner",
    "accounts",
    "high_risk_accounts",
    "open_tickets",
    "open_incidents",
    "overdue_playbooks",
    "engagement_gaps",
    "arr_at_risk",
    "next_playbook_due",
    "escalation_needed",
}

RECOVERY_FIELDS = {
    "account",
    "owner",
    "risk_band",
    "recovery_stage",
    "blocker_count",
    "action_due",
    "executive_touch_due",
    "arr",
    "recommended_action",
}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
RECOVERY_ORDER = {
    "contract_restore": 0,
    "incident_response": 1,
    "renewal_save": 2,
    "playbook_cleanup": 3,
    "engagement_restart": 4,
    "monitoring": 5,
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


def write_fixture(root: Path, *, variant: str) -> Path:
    data_dir = root / variant
    data_dir.mkdir()
    if variant == "hidden-a":
        write_json(
            data_dir / "accounts.json",
            [
                {"account_id": "ha-1", "name": "Atlas Cloud", "owner": "Rin Vale", "plan": "enterprise"},
                {"account_id": "ha-2", "name": "Beacon Foods", "owner": "Elle Ortiz", "plan": "pro"},
                {"account_id": "ha-3", "name": "Cinder Bank", "owner": "Rin Vale", "plan": "enterprise"},
                {"account_id": "ha-4", "name": "Drift Labs", "owner": "Samir Iqbal", "plan": "starter"},
                {"account_id": "ha-5", "name": "Ember Media", "owner": "Lina Fox", "plan": "pro"},
            ],
        )
        write_json(
            data_dir / "tickets.json",
            [
                {"ticket_id": "HA1-T1", "account_id": "ha-1", "status": "open"},
                {"ticket_id": "HA1-T2", "account_id": "ha-1", "status": "closed"},
                {"ticket_id": "HA2-T1", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T2", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T3", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T4", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA2-T5", "account_id": "ha-2", "status": "open"},
                {"ticket_id": "HA4-T1", "account_id": "ha-4", "status": "open"},
            ],
        )
        write_json(
            data_dir / "incidents.json",
            [
                {"incident_id": "HA1-I1", "account_id": "ha-1", "status": "open", "severity": "critical"},
                {"incident_id": "HA3-I1", "account_id": "ha-3", "status": "open", "severity": "minor"},
                {"incident_id": "HA5-I1", "account_id": "ha-5", "status": "resolved", "severity": "major"},
            ],
        )
        write_json(
            data_dir / "usage.json",
            [
                {"account_id": "ha-1", "previous_period_events": 5000, "current_period_events": 5200},
                {"account_id": "ha-2", "previous_period_events": 2200, "current_period_events": 1700},
                {"account_id": "ha-3", "previous_period_events": 1000, "current_period_events": 1040},
                {"account_id": "ha-4", "previous_period_events": 400, "current_period_events": 300},
                {"account_id": "ha-5", "previous_period_events": 750, "current_period_events": 750},
            ],
        )
        write_json(
            data_dir / "renewals.json",
            {
                "report_date": "2026-08-01",
                "renewals": [
                    {"account_id": "ha-1", "renewal_date": "2026-08-18"},
                    {"account_id": "ha-2", "renewal_date": "2026-12-20"},
                    {"account_id": "ha-3", "renewal_date": "2026-08-11"},
                    {"account_id": "ha-4", "renewal_date": "2026-09-18"},
                    {"account_id": "ha-5", "renewal_date": "2026-08-30"},
                ],
            },
        )
        write_json(
            data_dir / "contracts.json",
            {
                "contracts": [
                    {"account_id": "ha-1", "arr": 205000, "status": "active"},
                    {"account_id": "ha-2", "arr": 42000, "status": "active"},
                    {"account_id": "ha-3", "arr": 175000, "status": "trialing"},
                    {"account_id": "ha-4", "arr": 9000, "status": "suspended"},
                    {"account_id": "ha-5", "arr": 72000, "status": "active"},
                ]
            },
        )
        write_json(
            data_dir / "engagements.json",
            [
                {"account_id": "ha-1", "channel": "exec", "last_touch_at": "2026-07-29", "next_touch_at": "2026-08-05", "status": "scheduled"},
                {"account_id": "ha-2", "channel": "csm", "last_touch_at": "2026-05-01", "next_touch_at": "2026-07-15", "status": "missed"},
                {"account_id": "ha-3", "channel": "qbr", "last_touch_at": "2026-07-30", "next_touch_at": "2026-08-20", "status": "scheduled"},
                {"account_id": "ha-4", "channel": "csm", "last_touch_at": "2026-06-01", "next_touch_at": "2026-07-01", "status": "missed"},
                {"account_id": "ha-5", "channel": "exec", "last_touch_at": "2026-06-20", "next_touch_at": "2026-08-19", "status": "scheduled"},
            ],
        )
        write_json(
            data_dir / "playbooks.json",
            [
                {"account_id": "ha-1", "blockers": "incident follow-up", "due_date": "2026-08-02", "owner": "Rin Vale", "playbook": "renewal-save", "status": "open"},
                {"account_id": "ha-2", "blockers": "", "due_date": "2026-07-30", "owner": "Elle Ortiz", "playbook": "adoption-recovery", "status": "open"},
                {"account_id": "ha-3", "blockers": "", "due_date": "2026-08-10", "owner": "Rin Vale", "playbook": "exec-check", "status": "done"},
                {"account_id": "ha-4", "blockers": "contract inactive", "due_date": "2026-07-20", "owner": "Samir Iqbal", "playbook": "contract-restore", "status": "open"},
                {"account_id": "ha-4", "blockers": "owner review", "due_date": "2026-07-25", "owner": "Samir Iqbal", "playbook": "risk-review", "status": "open"},
            ],
        )
    else:
        write_json(
            data_dir / "accounts.json",
            [
                {"account_id": "hb-1", "name": "Northwind Systems", "owner": "Priya Sen", "plan": "enterprise"},
                {"account_id": "hb-2", "name": "Oak and Pine", "owner": "Theo Grant", "plan": "starter"},
                {"account_id": "hb-3", "name": "Pioneer Robotics", "owner": "Mika Lane", "plan": "pro"},
                {"account_id": "hb-4", "name": "Quartz Energy", "owner": "Priya Sen", "plan": "enterprise"},
            ],
        )
        write_json(
            data_dir / "tickets.json",
            [
                {"ticket_id": "HB1-T1", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T2", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T3", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T4", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB1-T5", "account_id": "hb-1", "status": "open"},
                {"ticket_id": "HB2-T1", "account_id": "hb-2", "status": "closed"},
                {"ticket_id": "HB3-T1", "account_id": "hb-3", "status": "open"},
                {"ticket_id": "HB4-T1", "account_id": "hb-4", "status": "open"},
            ],
        )
        write_json(
            data_dir / "incidents.json",
            [
                {"incident_id": "HB3-I1", "account_id": "hb-3", "status": "open", "severity": "major"},
                {"incident_id": "HB4-I1", "account_id": "hb-4", "status": "open", "severity": "minor"},
            ],
        )
        write_json(
            data_dir / "usage.json",
            [
                {"account_id": "hb-1", "previous_period_events": 1200, "current_period_events": 800},
                {"account_id": "hb-2", "previous_period_events": 500, "current_period_events": 505},
                {"account_id": "hb-3", "previous_period_events": 300, "current_period_events": 200},
                {"account_id": "hb-4", "previous_period_events": 1800, "current_period_events": 2100},
            ],
        )
        write_json(
            data_dir / "renewals.json",
            {
                "report_date": "2026-10-10",
                "renewals": [
                    {"account_id": "hb-1", "renewal_date": "2026-10-25"},
                    {"account_id": "hb-2", "renewal_date": "2026-12-30"},
                    {"account_id": "hb-3", "renewal_date": "2026-10-22"},
                    {"account_id": "hb-4", "renewal_date": "2026-11-15"},
                ],
            },
        )
        write_json(
            data_dir / "contracts.json",
            {
                "contracts": [
                    {"account_id": "hb-1", "arr": 310000, "status": "active"},
                    {"account_id": "hb-2", "arr": 8000, "status": "active"},
                    {"account_id": "hb-3", "arr": 56000, "status": "expired"},
                    {"account_id": "hb-4", "arr": 265000, "status": "trialing"},
                ]
            },
        )
        write_json(
            data_dir / "engagements.json",
            [
                {"account_id": "hb-1", "channel": "csm", "last_touch_at": "2026-08-10", "next_touch_at": "2026-09-20", "status": "missed"},
                {"account_id": "hb-1", "channel": "exec", "last_touch_at": "2026-10-01", "next_touch_at": "2026-10-15", "status": "scheduled"},
                {"account_id": "hb-2", "channel": "csm", "last_touch_at": "2026-09-01", "next_touch_at": "2026-10-20", "status": "scheduled"},
                {"account_id": "hb-3", "channel": "exec", "last_touch_at": "2026-09-25", "next_touch_at": "2026-10-05", "status": "missed"},
                {"account_id": "hb-4", "channel": "qbr", "last_touch_at": "2026-09-28", "next_touch_at": "2026-11-05", "status": "scheduled"},
            ],
        )
        write_json(
            data_dir / "playbooks.json",
            [
                {"account_id": "hb-1", "blockers": "", "due_date": "2026-10-12", "owner": "Priya Sen", "playbook": "renewal-save", "status": "open"},
                {"account_id": "hb-3", "blockers": "contract expired", "due_date": "2026-10-01", "owner": "Mika Lane", "playbook": "contract-restore", "status": "open"},
                {"account_id": "hb-3", "blockers": "", "due_date": "2026-10-18", "owner": "Mika Lane", "playbook": "incident-follow-up", "status": "open"},
                {"account_id": "hb-4", "blockers": "", "due_date": "2026-10-07", "owner": "Priya Sen", "playbook": "exec-check", "status": "done"},
            ],
        )
    return data_dir


def load_json(data_dir: Path, name: str) -> object:
    return json.loads((data_dir / name).read_text())


def metric_values(raw: dict[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, text in raw.items():
        match = re.search(r"(-?\d+)$", text.strip())
        values[key] = match.group(1) if match else text.strip()
    return values


def band(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def build_model(data_dir: Path) -> tuple[object, ...]:
    accounts = load_json(data_dir, "accounts.json")
    tickets = load_json(data_dir, "tickets.json")
    incidents = load_json(data_dir, "incidents.json")
    usage = {row["account_id"]: row for row in load_json(data_dir, "usage.json")}
    renewal_payload = load_json(data_dir, "renewals.json")
    report_date = date.fromisoformat(renewal_payload["report_date"])
    renewals = {row["account_id"]: row for row in renewal_payload["renewals"]}
    contracts = {row["account_id"]: row for row in load_json(data_dir, "contracts.json")["contracts"]}
    engagements_raw = load_json(data_dir, "engagements.json")
    playbooks = load_json(data_dir, "playbooks.json")

    open_tickets: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket["status"] == "open":
            open_tickets[ticket["account_id"]] += 1

    open_incidents: dict[str, int] = defaultdict(int)
    for incident in incidents:
        if incident["status"] == "open" and incident["severity"] in {"major", "critical"}:
            open_incidents[incident["account_id"]] += 1

    latest_engagement: dict[str, dict[str, str]] = {}
    for engagement in engagements_raw:
        account_id = engagement["account_id"]
        current = latest_engagement.get(account_id)
        if current is None or engagement["last_touch_at"] > current["last_touch_at"]:
            latest_engagement[account_id] = engagement

    open_playbook_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for playbook in playbooks:
        if playbook["status"] != "done":
            open_playbook_rows[playbook["account_id"]].append(playbook)

    rows: list[dict[str, object]] = []
    for account in accounts:
        account_id = account["account_id"]
        renewal_date = date.fromisoformat(renewals[account_id]["renewal_date"])
        days = (renewal_date - report_date).days
        account_usage = usage[account_id]
        usage_down = account_usage["current_period_events"] < account_usage["previous_period_events"]
        usage_up = account_usage["current_period_events"] > account_usage["previous_period_events"]
        ticket_count = open_tickets[account_id]
        incident_count = open_incidents[account_id]
        contract = contracts[account_id]
        contract_status = contract["status"]
        contract_active = contract_status in {"active", "trialing"}
        renewal_date_text = renewals[account_id]["renewal_date"]
        account_playbooks = open_playbook_rows[account_id]
        overdue_playbooks = sum(1 for item in account_playbooks if item["due_date"] <= renewal_payload["report_date"])
        next_playbook_due = min((item["due_date"] for item in account_playbooks), default="")
        engagement = latest_engagement.get(account_id)
        if engagement is None:
            engagement_gap = "yes"
        else:
            last_touch = date.fromisoformat(engagement["last_touch_at"])
            next_touch = date.fromisoformat(engagement["next_touch_at"])
            engagement_gap = "yes" if (report_date - last_touch).days > 45 or next_touch < report_date else "no"

        score = 0
        if days <= 30:
            score += 40
        if incident_count:
            score += 25
        score += min(30, ticket_count * 6)
        if usage_down:
            score += 20
        if account["plan"] == "enterprise" and usage_up:
            score -= 10
        if not contract_active:
            score += 35
        if overdue_playbooks:
            score += 20
        if engagement_gap == "yes":
            score += 15
        score = min(100, max(0, score))
        risk_band = band(score)

        if not contract_active:
            action = "Restore contract"
        elif incident_count:
            action = "Escalate incident response"
        elif overdue_playbooks:
            action = "Clear customer plan blockers"
        elif days <= 30 and risk_band == "high":
            action = "Schedule renewal save plan"
        elif ticket_count >= 4:
            action = "Clear support queue"
        elif engagement_gap == "yes":
            action = "Re-engage account owner"
        elif usage_down:
            action = "Review adoption drop"
        else:
            action = "Monitor"

        if not contract_active:
            recovery_stage = "contract_restore"
        elif incident_count:
            recovery_stage = "incident_response"
        elif days <= 30 and risk_band == "high":
            recovery_stage = "renewal_save"
        elif overdue_playbooks:
            recovery_stage = "playbook_cleanup"
        elif engagement_gap == "yes":
            recovery_stage = "engagement_restart"
        else:
            recovery_stage = "monitoring"
        blocker_count = incident_count + overdue_playbooks
        if not contract_active:
            blocker_count += 1
        if engagement_gap == "yes":
            blocker_count += 1
        if next_playbook_due:
            action_due = next_playbook_due
        elif recovery_stage in {"contract_restore", "incident_response"}:
            action_due = renewal_payload["report_date"]
        elif recovery_stage == "renewal_save":
            action_due = renewal_date_text
        else:
            action_due = ""
        executive_touch_due = (
            "yes"
            if int(contract["arr"]) >= 100000
            and (risk_band != "low" or days <= 30)
            else "no"
        )

        rows.append(
            {
                "account_id": account_id,
                "name": account["name"],
                "owner": account["owner"],
                "plan": account["plan"],
                "risk_score": score,
                "risk_band": risk_band,
                "open_ticket_count": ticket_count,
                "open_incident_count": incident_count,
                "days_until_renewal": days,
                "arr": contract["arr"],
                "contract_status": contract_status,
                "engagement_gap": engagement_gap,
                "open_playbooks": len(account_playbooks),
                "overdue_playbooks": overdue_playbooks,
                "next_playbook_due": next_playbook_due,
                "recommended_action": action,
                "renewal_date": renewal_date_text,
                "recovery_stage": recovery_stage,
                "blocker_count": blocker_count,
                "action_due": action_due,
                "executive_touch_due": executive_touch_due,
            }
        )

    rows.sort(key=lambda row: (-int(row["risk_score"]), int(row["days_until_renewal"]), str(row["name"])))
    dashboard_metrics = {
        "accounts": len(rows),
        "high-risk": sum(row["risk_band"] == "high" for row in rows),
        "open-tickets": sum(int(row["open_ticket_count"]) for row in rows),
        "renewals-30d": sum(0 <= int(row["days_until_renewal"]) <= 30 for row in rows),
    }

    action_rows = [
        {
            "account_id": row["account_id"],
            "account": row["name"],
            "owner": row["owner"],
            "risk_band": row["risk_band"],
            "recommended_action": row["recommended_action"],
            "next_playbook_due": row["next_playbook_due"],
            "overdue_playbooks": row["overdue_playbooks"],
            "open_playbooks": row["open_playbooks"],
            "arr": row["arr"],
            "engagement_gap": row["engagement_gap"],
        }
        for row in rows
        if row["recommended_action"] != "Monitor" or int(row["open_playbooks"]) > 0
    ]
    action_rows.sort(
        key=lambda row: (
            SEVERITY_ORDER[str(row["risk_band"])],
            -int(row["overdue_playbooks"]),
            str(row["next_playbook_due"]) == "",
            str(row["next_playbook_due"]),
            str(row["account"]),
        )
    )
    action_metrics = {
        "actions": len(action_rows),
        "overdue-playbooks": sum(int(row["overdue_playbooks"]) for row in action_rows),
        "engagement-gaps": sum(row["engagement_gap"] == "yes" for row in action_rows),
        "arr-at-risk": sum(int(row["arr"]) for row in action_rows if row["risk_band"] != "low"),
    }

    owners: dict[str, dict[str, object]] = {}
    for row in rows:
        owner = str(row["owner"])
        bucket = owners.setdefault(
            owner,
            {
                "owner": owner,
                "accounts": 0,
                "high_risk_accounts": 0,
                "open_tickets": 0,
                "open_incidents": 0,
                "overdue_playbooks": 0,
                "engagement_gaps": 0,
                "arr_at_risk": 0,
                "next_playbook_due": "",
                "escalation_needed": "no",
            },
        )
        bucket["accounts"] = int(bucket["accounts"]) + 1
        bucket["high_risk_accounts"] = int(bucket["high_risk_accounts"]) + (1 if row["risk_band"] == "high" else 0)
        bucket["open_tickets"] = int(bucket["open_tickets"]) + int(row["open_ticket_count"])
        bucket["open_incidents"] = int(bucket["open_incidents"]) + int(row["open_incident_count"])
        bucket["overdue_playbooks"] = int(bucket["overdue_playbooks"]) + int(row["overdue_playbooks"])
        bucket["engagement_gaps"] = int(bucket["engagement_gaps"]) + (1 if row["engagement_gap"] == "yes" else 0)
        if row["risk_band"] != "low":
            bucket["arr_at_risk"] = int(bucket["arr_at_risk"]) + int(row["arr"])
        due = str(row["next_playbook_due"])
        if due and (not bucket["next_playbook_due"] or due < str(bucket["next_playbook_due"])):
            bucket["next_playbook_due"] = due

    owner_rows = list(owners.values())
    for row in owner_rows:
        if int(row["high_risk_accounts"]) >= 1 or int(row["overdue_playbooks"]) >= 2 or int(row["open_incidents"]) >= 1:
            row["escalation_needed"] = "yes"
    owner_rows.sort(
        key=lambda row: (
            0 if row["escalation_needed"] == "yes" else 1,
            -int(row["arr_at_risk"]),
            str(row["owner"]),
        )
    )
    owner_metrics = {
        "owners": len(owner_rows),
        "owners-with-escalations": sum(row["escalation_needed"] == "yes" for row in owner_rows),
        "overdue-playbooks": sum(int(row["overdue_playbooks"]) for row in owner_rows),
        "arr-at-risk": sum(int(row["arr_at_risk"]) for row in owner_rows),
    }

    recovery_rows = [
        {
            "account_id": row["account_id"],
            "account": row["name"],
            "owner": row["owner"],
            "risk_band": row["risk_band"],
            "recovery_stage": row["recovery_stage"],
            "blocker_count": row["blocker_count"],
            "action_due": row["action_due"],
            "executive_touch_due": row["executive_touch_due"],
            "arr": row["arr"],
            "recommended_action": row["recommended_action"],
        }
        for row in rows
        if row["recovery_stage"] != "monitoring" or row["risk_band"] != "low"
    ]
    recovery_rows.sort(
        key=lambda row: (
            RECOVERY_ORDER[str(row["recovery_stage"])],
            -int(row["blocker_count"]),
            str(row["action_due"]) == "",
            str(row["action_due"]),
            str(row["account"]),
        )
    )
    recovery_metrics = {
        "recovery-accounts": len(recovery_rows),
        "blocked-plans": sum(
            row["recovery_stage"] in {"contract_restore", "incident_response"}
            for row in recovery_rows
        ),
        "exec-touches": sum(row["executive_touch_due"] == "yes" for row in recovery_rows),
        "arr-in-plan": sum(int(row["arr"]) for row in recovery_rows),
    }
    dashboard_export_rows = [
        {
            "account_id": row["account_id"],
            "name": row["name"],
            "owner": row["owner"],
            "plan": row["plan"],
            "risk_score": row["risk_score"],
            "risk_band": row["risk_band"],
            "open_ticket_count": row["open_ticket_count"],
            "open_incident_count": row["open_incident_count"],
            "days_until_renewal": row["days_until_renewal"],
            "arr": row["arr"],
            "contract_status": row["contract_status"],
            "engagement_gap": row["engagement_gap"],
            "open_playbooks": row["open_playbooks"],
            "overdue_playbooks": row["overdue_playbooks"],
            "next_playbook_due": row["next_playbook_due"],
            "recommended_action": row["recommended_action"],
        }
        for row in rows
    ]
    export_payload = {
        "report_date": renewal_payload["report_date"],
        "dashboard_rows": dashboard_export_rows,
        "action_rows": action_rows,
        "owner_rows": owner_rows,
        "recovery_rows": recovery_rows,
        "summary": {
            "accounts": dashboard_metrics["accounts"],
            "high_risk": dashboard_metrics["high-risk"],
            "actions": action_metrics["actions"],
            "owners_with_escalations": owner_metrics["owners-with-escalations"],
            "recovery_accounts": recovery_metrics["recovery-accounts"],
            "arr_at_risk": owner_metrics["arr-at-risk"],
            "arr_in_recovery": recovery_metrics["arr-in-plan"],
        },
    }
    return (
        rows,
        dashboard_metrics,
        action_rows,
        action_metrics,
        owner_rows,
        owner_metrics,
        recovery_rows,
        recovery_metrics,
        export_payload,
    )


class HealthParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, object] | None] = []
        self.h1: list[str] = []
        self.screens: set[str] = set()
        self.tables: set[str] = set()
        self.nav_links: list[tuple[str, str]] = []
        self.metrics: dict[str, str] = defaultdict(str)
        self.account_rows: dict[str, dict[str, str]] = defaultdict(lambda: defaultdict(str))
        self.account_order: list[str] = []
        self.owner_rows: dict[str, dict[str, str]] = defaultdict(lambda: defaultdict(str))
        self.owner_order: list[str] = []

    def _current_row(self) -> tuple[str, str] | None:
        for item in reversed(self.stack):
            if item and item[0] == "account-row":
                return ("account", str(item[1]))
            if item and item[0] == "owner-row":
                return ("owner", str(item[1]))
        return None

    def handle_starttag(self, tag: str, attrs_raw: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_raw}
        capture: tuple[str, object] | None = None
        if tag == "main" and attrs.get("data-screen"):
            self.screens.add(attrs["data-screen"])
        if tag == "table" and attrs.get("data-table"):
            self.tables.add(attrs["data-table"])
        if tag == "h1":
            capture = ("h1", None)
        elif tag == "a" and attrs.get("href"):
            capture = ("nav", attrs["href"])
        elif "data-metric" in attrs:
            capture = ("metric", attrs["data-metric"])
        elif tag == "tr" and "data-account-id" in attrs:
            account_id = attrs["data-account-id"]
            capture = ("account-row", account_id)
            self.account_order.append(account_id)
        elif tag == "tr" and "data-owner" in attrs:
            owner = attrs["data-owner"]
            capture = ("owner-row", owner)
            self.owner_order.append(owner)
        elif "data-field" in attrs:
            current = self._current_row()
            if current is not None:
                row_type, row_id = current
                if row_type == "account":
                    self.account_rows[str(row_id)][attrs["data-field"]] += ""
                else:
                    self.owner_rows[str(row_id)][attrs["data-field"]] += ""
                capture = ("field", (row_type, row_id, attrs["data-field"]))
        self.stack.append(capture)

    def handle_endtag(self, tag: str) -> None:
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        for item in reversed(self.stack):
            if item is None:
                continue
            kind, payload = item
            if kind == "h1":
                self.h1.append(text)
                return
            if kind == "nav":
                self.nav_links.append((text, str(payload)))
                return
            if kind == "metric":
                self.metrics[str(payload)] += text
                return
            if kind == "field":
                row_type, row_id, field = payload
                if row_type == "account":
                    self.account_rows[str(row_id)][str(field)] += text
                else:
                    self.owner_rows[str(row_id)][str(field)] += text
                return


def render(route: str, data_dir: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "out.html"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "workspace_app.cli",
                "--route",
                route,
                "--data-dir",
                str(data_dir),
                "--output",
                str(output),
            ],
            check=True,
        )
        return output.read_text()


def export_customer_health(data_dir: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "customer-health.json"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "workspace_app.cli",
                "--data-dir",
                str(data_dir),
                "--export-customer-health",
                str(output),
            ],
            check=True,
        )
        return json.loads(output.read_text())


def parse(html: str) -> HealthParser:
    parser = HealthParser()
    parser.feed(html)
    return parser


class CustomerHealthVerifier(unittest.TestCase):
    def assert_dashboard(self, data_dir: Path) -> None:
        rows, metrics, *_ = build_model(data_dir)
        parser = parse(render("/customer-health", data_dir))
        self.assertIn("customer-health", parser.screens)
        self.assertIn("customer-health-risks", parser.tables)
        self.assertIn(("Customer Health", "/customer-health"), parser.nav_links)
        self.assertEqual(" ".join(parser.h1), "Customer Health")
        self.assertEqual(metric_values(parser.metrics), {key: str(value) for key, value in metrics.items()})
        self.assertEqual(parser.account_order, [str(row["account_id"]) for row in rows])
        self.assertEqual(set(parser.account_rows), {str(row["account_id"]) for row in rows})
        for row in rows:
            account_id = str(row["account_id"])
            self.assertEqual(set(parser.account_rows[account_id]), DASHBOARD_FIELDS)
            for field in DASHBOARD_FIELDS:
                self.assertEqual(parser.account_rows[account_id][field], str(row[field]), (account_id, field))

    def assert_actions(self, data_dir: Path) -> None:
        _, _, rows, metrics, *_ = build_model(data_dir)
        parser = parse(render("/customer-health/actions", data_dir))
        self.assertIn("customer-health-actions", parser.screens)
        self.assertIn("customer-health-actions", parser.tables)
        self.assertEqual(" ".join(parser.h1), "Customer Health Actions")
        self.assertEqual(metric_values(parser.metrics), {key: str(value) for key, value in metrics.items()})
        self.assertEqual(parser.account_order, [str(row["account_id"]) for row in rows])
        self.assertEqual(set(parser.account_rows), {str(row["account_id"]) for row in rows})
        for row in rows:
            account_id = str(row["account_id"])
            self.assertEqual(set(parser.account_rows[account_id]), ACTIONS_FIELDS)
            for field in ACTIONS_FIELDS:
                self.assertEqual(parser.account_rows[account_id][field], str(row[field]), (account_id, field))

    def assert_owner_queue(self, data_dir: Path) -> None:
        _, _, _, _, rows, metrics, *_ = build_model(data_dir)
        parser = parse(render("/customer-health/owner-queue", data_dir))
        self.assertIn("customer-health-owner-queue", parser.screens)
        self.assertIn("customer-health-owner-queue", parser.tables)
        self.assertEqual(" ".join(parser.h1), "Customer Health Owner Queue")
        self.assertEqual(metric_values(parser.metrics), {key: str(value) for key, value in metrics.items()})
        self.assertEqual(parser.owner_order, [str(row["owner"]) for row in rows])
        self.assertEqual(set(parser.owner_rows), {str(row["owner"]) for row in rows})
        for row in rows:
            owner = str(row["owner"])
            self.assertEqual(set(parser.owner_rows[owner]), OWNER_FIELDS)
            for field in OWNER_FIELDS:
                self.assertEqual(parser.owner_rows[owner][field], str(row[field]), (owner, field))

    def assert_recovery_plan(self, data_dir: Path) -> None:
        *_, rows, metrics, _ = build_model(data_dir)
        parser = parse(render("/customer-health/recovery-plan", data_dir))
        self.assertIn("customer-health-recovery-plan", parser.screens)
        self.assertIn("customer-health-recovery-plan", parser.tables)
        self.assertEqual(" ".join(parser.h1), "Customer Health Recovery Plan")
        self.assertEqual(metric_values(parser.metrics), {key: str(value) for key, value in metrics.items()})
        self.assertEqual(parser.account_order, [str(row["account_id"]) for row in rows])
        self.assertEqual(set(parser.account_rows), {str(row["account_id"]) for row in rows})
        for row in rows:
            account_id = str(row["account_id"])
            self.assertEqual(set(parser.account_rows[account_id]), RECOVERY_FIELDS)
            for field in RECOVERY_FIELDS:
                self.assertEqual(parser.account_rows[account_id][field], str(row[field]), (account_id, field))

    def assert_export(self, data_dir: Path) -> None:
        *_, expected_export = build_model(data_dir)
        actual = export_customer_health(data_dir)
        self.assertEqual(set(actual), {"report_date", "dashboard_rows", "action_rows", "owner_rows", "recovery_rows", "summary"})
        self.assertEqual(actual, expected_export)

    def assert_all_routes(self, data_dir: Path) -> None:
        self.assert_dashboard(data_dir)
        self.assert_actions(data_dir)
        self.assert_owner_queue(data_dir)
        self.assert_recovery_plan(data_dir)
        self.assert_export(data_dir)

    def test_source_structure_and_unittest_regression(self) -> None:
        for relative in [
            "workspace_app/screens/customer_health.py",
            "workspace_app/screens/customer_health_actions.py",
            "workspace_app/screens/customer_health_owner_queue.py",
            "workspace_app/screens/customer_health_recovery_plan.py",
            "workspace_app/selectors/customer_health.py",
        ]:
            self.assertTrue(Path("/app", relative).exists(), relative)
        test_files = list(Path("/app/tests").glob("test*.py"))
        combined_tests = "\n".join(path.read_text() for path in test_files)
        for route in [
            "/customer-health",
            "/customer-health/actions",
            "/customer-health/owner-queue",
            "/customer-health/recovery-plan",
            "--export-customer-health",
        ]:
            self.assertIn(route, combined_tests)
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], check=True)

    def test_existing_routes_still_render_and_nav_includes_new_item(self) -> None:
        for route, screen in [
            ("/", "home"),
            ("/accounts", "accounts"),
            ("/support", "support"),
            ("/billing", "billing"),
            ("/reports", "reports"),
        ]:
            with self.subTest(route=route):
                html = render(route, Path("/app/fixtures/visible"))
                self.assertIn(f'data-screen="{screen}"', html)
                self.assertIn('href="/customer-health"', html)
                self.assertIn("Customer Health", html)

    def test_visible_fixture_exact(self) -> None:
        self.assert_all_routes(Path("/app/fixtures/visible"))

    def test_hidden_fixtures_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assert_all_routes(write_fixture(root, variant="hidden-a"))
            self.assert_all_routes(write_fixture(root, variant="hidden-b"))


if __name__ == "__main__":
    unittest.main()
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"

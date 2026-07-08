#!/usr/bin/env bash
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"

python3 - <<'PY'
from pathlib import Path
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

app = Path(os.environ.get("APP_DIR", "/app"))
ALLOWED_REJECT_REASONS = {
    "duplicate_event",
    "invalid_timestamp",
    "malformed_line",
    "missing_field",
    "unknown_action",
    "unknown_actor",
}
SUMMARY_KEYS = {"actions", "actors", "rejected", "reject_reasons", "rows", "sources"}


def run_script(root: Path) -> None:
    subprocess.run([sys.executable, str(root / "scripts" / "build_outputs.py")], cwd=root, check=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    assert path.exists(), f"missing {path}"
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def assert_csv(path: Path, expected: list[dict[str, str]]) -> None:
    actual = read_csv(path)
    assert actual == expected, f"{path} mismatch:\nactual={actual!r}\nexpected={expected!r}"


def assert_json(path: Path, expected: object) -> None:
    assert path.exists(), f"missing {path}"
    actual = json.loads(path.read_text())
    assert actual == expected, f"{path} mismatch:\nactual={actual!r}\nexpected={expected!r}"


def assert_summary_json(path: Path, expected: object) -> None:
    assert path.exists(), f"missing {path}"
    actual = json.loads(path.read_text())
    assert set(actual) == SUMMARY_KEYS, f"{path} top-level keys mismatch: {sorted(actual)}"
    actual_reasons = actual.get("reject_reasons")
    assert isinstance(actual_reasons, dict), f"{path} reject_reasons must be an object"
    extra_reasons = set(actual_reasons) - ALLOWED_REJECT_REASONS
    assert not extra_reasons, f"{path} unknown reject reasons: {sorted(extra_reasons)}"
    actual = {
        **actual,
        "reject_reasons": {key: value for key, value in actual_reasons.items() if value != 0},
    }
    assert actual == expected, f"{path} mismatch:\nactual={actual!r}\nexpected={expected!r}"


def assert_visible_outputs(root: Path) -> None:
    assert_csv(
        root / "output" / "normalized.csv",
        [
            {
                "timestamp": "2026-07-04T08:05:00Z",
                "actor_id": "u_grace",
                "actor_name": "Grace Hopper",
                "action": "password_reset",
                "result": "ok",
                "event_id": "evt-002",
                "source": "app.pipe.log",
            },
            {
                "timestamp": "2026-07-04T10:00:00Z",
                "actor_id": "u_ada",
                "actor_name": "Ada Lovelace",
                "action": "user_login",
                "result": "ok",
                "event_id": "evt-001",
                "source": "app.pipe.log",
            },
            {
                "timestamp": "2026-07-04T10:02:00Z",
                "actor_id": "u_ada",
                "actor_name": "Ada Lovelace",
                "action": "user_login",
                "result": "ok",
                "event_id": "evt-003",
                "source": "admin.jsonl",
            },
            {
                "timestamp": "2026-07-04T10:03:00Z",
                "actor_id": "u_linus",
                "actor_name": "Linus Torvalds",
                "action": "export_csv",
                "result": "denied",
                "event_id": "evt-004",
                "source": "app.pipe.log",
            },
            {
                "timestamp": "2026-07-04T10:04:00Z",
                "actor_id": "u_margaret",
                "actor_name": "Margaret Hamilton",
                "action": "role_change",
                "result": "ok",
                "event_id": "evt-005",
                "source": "admin.jsonl",
            },
            {
                "timestamp": "2026-07-04T10:09:00Z",
                "actor_id": "u_margaret",
                "actor_name": "Margaret Hamilton",
                "action": "mfa_enrolled",
                "result": "ok",
                "event_id": "evt-009",
                "source": "legacy.csv",
            },
            {
                "timestamp": "2026-07-04T14:08:00Z",
                "actor_id": "u_ada",
                "actor_name": "Ada Lovelace",
                "action": "api_token_created",
                "result": "ok",
                "event_id": "evt-008",
                "source": "legacy.csv",
            },
        ],
    )
    assert_csv(
        root / "output" / "rejects.csv",
        [
            {
                "source": "admin.jsonl",
                "line": '{"timestamp":"2026-07-04T10:06:00Z","actor":"unknown@example.com","action":"LOGIN","result":"ok","event_id":"evt-006"}',
                "reason": "unknown_actor",
            },
            {
                "source": "admin.jsonl",
                "line": '{"timestamp":"2026-07-04T10:07:00Z","actor":"Grace","action":"missing-action","result":"ok","event_id":"evt-007"}',
                "reason": "unknown_action",
            },
            {"source": "admin.jsonl", "line": "not-json", "reason": "malformed_line"},
            {"source": "app.pipe.log", "line": "bad row", "reason": "malformed_line"},
            {
                "source": "app.pipe.log",
                "line": "2026-07-04T10:03:00Z|Linus|Export CSV|denied|evt-004",
                "reason": "duplicate_event",
            },
            {
                "source": "legacy.csv",
                "line": "2026-07-04T10:10:00Z,Grace,User Login,failed,",
                "reason": "missing_field",
            },
        ],
    )
    assert_summary_json(
        root / "output" / "summary.json",
        {
            "actions": {
                "api_token_created": 1,
                "export_csv": 1,
                "mfa_enrolled": 1,
                "password_reset": 1,
                "role_change": 1,
                "user_login": 2,
            },
            "actors": {"u_ada": 3, "u_grace": 1, "u_linus": 1, "u_margaret": 2},
            "rejected": 6,
            "reject_reasons": {
                "duplicate_event": 1,
                "malformed_line": 2,
                "missing_field": 1,
                "unknown_action": 1,
                "unknown_actor": 1,
            },
            "rows": 7,
            "sources": {"admin.jsonl": 2, "app.pipe.log": 3, "legacy.csv": 2},
        },
    )


def copy_script_to_hidden(root: Path) -> None:
    (root / "input" / "sources").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(app / "scripts" / "build_outputs.py", root / "scripts" / "build_outputs.py")
    (root / "input" / "actors.csv").write_text(
        "actor_id,name,email,aliases\n"
        "u_bea,Bea Kim,bea@example.com,Beatrice\n"
        "u_omar,Omar Ali,omar@example.com,O. Ali\n"
        "u_nia,Nia Chen,nia@example.com,Nia\n"
    )
    (root / "input" / "action_aliases.csv").write_text(
        "raw,canonical\n"
        "Sign In,sign_in\n"
        "EXPORT,export_csv\n"
        "Policy Update,policy_update\n"
        "Token Revoked,token_revoked\n"
    )
    (root / "input" / "sources" / "01.csv").write_text(
        "timestamp,actor,action,result,event_id\n"
        "2026-07-05T09:00:00Z,Beatrice,Sign In,OK,h-001\n"
        "2026-07-05T09:01:00+01:00,omar@example.com,EXPORT,DENIED,h-002\n"
        "2026-07-05T09:02:00Z,Nia,Unknown,ok,h-003\n"
        ",Beatrice,Sign In,ok,h-004\n"
    )
    (root / "input" / "sources" / "02.pipe.log").write_text(
        "2026-07-05T09:03:00Z|u_nia|Policy Update|ok|h-005\n"
        "2026-07-05T09:04:00Z|ghost|Sign In|ok|h-006\n"
        "2026-07-05T09:05:00Z|u_bea|Token Revoked|FAILED|h-005\n"
        "bad|too|few\n"
    )
    (root / "input" / "sources" / "03.jsonl").write_text(
        '{"timestamp":"2026-07-05T09:06:00-04:00","actor":"O. Ali","action":"Token Revoked","result":"ok","event_id":"h-007"}\n'
        '{"timestamp":"2026-07-05T09:07:00","actor":"Bea Kim","action":"Sign In","result":"ok","event_id":"h-008"}\n'
        '{"timestamp":"2026-07-05T09:08:00Z","actor":"Nia","action":"Sign In","result":"","event_id":"h-009"}\n'
        "not-json\n"
    )


def assert_hidden_outputs(root: Path) -> None:
    assert_csv(
        root / "output" / "normalized.csv",
        [
            {
                "timestamp": "2026-07-05T08:01:00Z",
                "actor_id": "u_omar",
                "actor_name": "Omar Ali",
                "action": "export_csv",
                "result": "denied",
                "event_id": "h-002",
                "source": "01.csv",
            },
            {
                "timestamp": "2026-07-05T09:00:00Z",
                "actor_id": "u_bea",
                "actor_name": "Bea Kim",
                "action": "sign_in",
                "result": "ok",
                "event_id": "h-001",
                "source": "01.csv",
            },
            {
                "timestamp": "2026-07-05T09:03:00Z",
                "actor_id": "u_nia",
                "actor_name": "Nia Chen",
                "action": "policy_update",
                "result": "ok",
                "event_id": "h-005",
                "source": "02.pipe.log",
            },
            {
                "timestamp": "2026-07-05T13:06:00Z",
                "actor_id": "u_omar",
                "actor_name": "Omar Ali",
                "action": "token_revoked",
                "result": "ok",
                "event_id": "h-007",
                "source": "03.jsonl",
            },
        ],
    )
    assert_csv(
        root / "output" / "rejects.csv",
        [
            {
                "source": "01.csv",
                "line": "2026-07-05T09:02:00Z,Nia,Unknown,ok,h-003",
                "reason": "unknown_action",
            },
            {"source": "01.csv", "line": ",Beatrice,Sign In,ok,h-004", "reason": "missing_field"},
            {
                "source": "02.pipe.log",
                "line": "2026-07-05T09:04:00Z|ghost|Sign In|ok|h-006",
                "reason": "unknown_actor",
            },
            {
                "source": "02.pipe.log",
                "line": "2026-07-05T09:05:00Z|u_bea|Token Revoked|FAILED|h-005",
                "reason": "duplicate_event",
            },
            {"source": "02.pipe.log", "line": "bad|too|few", "reason": "malformed_line"},
            {
                "source": "03.jsonl",
                "line": '{"timestamp":"2026-07-05T09:07:00","actor":"Bea Kim","action":"Sign In","result":"ok","event_id":"h-008"}',
                "reason": "invalid_timestamp",
            },
            {
                "source": "03.jsonl",
                "line": '{"timestamp":"2026-07-05T09:08:00Z","actor":"Nia","action":"Sign In","result":"","event_id":"h-009"}',
                "reason": "missing_field",
            },
            {"source": "03.jsonl", "line": "not-json", "reason": "malformed_line"},
        ],
    )
    assert_summary_json(
        root / "output" / "summary.json",
        {
            "actions": {
                "export_csv": 1,
                "policy_update": 1,
                "sign_in": 1,
                "token_revoked": 1,
            },
            "actors": {"u_bea": 1, "u_nia": 1, "u_omar": 2},
            "rejected": 8,
            "reject_reasons": {
                "duplicate_event": 1,
                "invalid_timestamp": 1,
                "malformed_line": 2,
                "missing_field": 2,
                "unknown_action": 1,
                "unknown_actor": 1,
            },
            "rows": 4,
            "sources": {"01.csv": 2, "02.pipe.log": 1, "03.jsonl": 1},
        },
    )


script = app / "scripts" / "build_outputs.py"
assert script.exists(), "missing scripts/build_outputs.py"
run_script(app)
assert_visible_outputs(app)

with tempfile.TemporaryDirectory() as tmp:
    hidden = Path(tmp) / "app"
    copy_script_to_hidden(hidden)
    run_script(hidden)
    assert_hidden_outputs(hidden)
PY

status=$?
if [[ $status -eq 0 ]]; then
  echo 1 > "$LOG_DIR/reward.txt"
else
  echo 0 > "$LOG_DIR/reward.txt"
fi
exit "$status"

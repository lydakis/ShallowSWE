#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

cat > "$APP_DIR/webhook_sync/events.py" <<'PY'
from __future__ import annotations


def initial_state():
    return {"processed_event_ids": [], "total_cents": 0, "orders": {}}


def _event_seen(state, event_id):
    processed = state.setdefault("processed_event_ids", [])
    if event_id in processed:
        return True
    processed.append(event_id)
    return False


def _apply_once(event, state):
    if _event_seen(state, event["event_id"]):
        return state
    state["total_cents"] += event["amount_cents"]
    state["orders"][event["order_id"]] = event["status"]
    return state


def apply_import(events, state):
    for event in events:
        _apply_once(event, state)
    return state


def apply_webhook(event, state):
    return _apply_once(event, state)


def replay_events(events, state):
    for event in events:
        _apply_once(event, state)
    return state
PY

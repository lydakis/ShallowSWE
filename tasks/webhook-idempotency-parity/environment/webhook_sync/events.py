def initial_state(): return {"processed_event_ids": [], "total_cents": 0, "orders": {}}
def apply_import(events, state):
    processed=state.setdefault("processed_event_ids", [])
    for event in events:
        if event["event_id"] in processed: continue
        processed.append(event["event_id"]); state["total_cents"] += event["amount_cents"]; state["orders"][event["order_id"]]=event["status"]
    return state
def apply_webhook(event, state):
    state.setdefault("processed_event_ids", []).append(event["event_id"]); state["total_cents"] += event["amount_cents"]; state["orders"][event["order_id"]]=event["status"]; return state
def replay_events(events, state):
    for event in events: apply_webhook(event, state)
    return state

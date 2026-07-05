# Update Existing Ticket Without Duplicate

A matching checkout bug ticket already exists. Update it with the new report details and do not create a duplicate ticket.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- Ticket count stays at one.
- Existing ticket `T-101` gets priority `P0` and a new comment.
- Call log records update, not create.
- Do not create any new ticket records.
- Add one non-empty comment to the matching existing ticket that summarizes the new report.
- The comment should mention saved-card coupon purchases, but the prose does not need to match an exact sentence.
- Write the call log as exactly one line using the matched ticket id:
  `update_ticket <ticket_id> priority=P0`

Keep the work local to this repository. Do not use network access.

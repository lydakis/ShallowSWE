# Update Existing Ticket Without Duplicate

A matching checkout bug ticket already exists. Update it with the new report details and do not create a duplicate ticket.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- Ticket count stays at one.
- Existing ticket `T-101` gets priority `P0` and a new comment.
- Call log records update, not create.

Keep the work local to this repository. Do not use network access.

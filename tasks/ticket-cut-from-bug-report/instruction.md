# Create Ticket From Bug Report

Read `bug_report.md` and update the local mock API state in `api_state/`.

Create exactly one open bug ticket and record the create call.

Write exactly one object to `api_state/tickets.json` with fields `component`, `id`, `labels`,
`priority`, `status`, and `title`.

Use these deterministic rules:

- If the report mentions checkout, use component `checkout`, id `T-100`, and title
  `Checkout 500 with saved card after coupon`.
- If the report mentions billing or payout, use component `billing`, id `T-200`, and title
  `Billing payout retry failure`.
- Use priority `P1`.
- Use labels `bug` and the component, in that order.
- Use status `open`.
Write this exact call log line to `api_state/calls.log`: `create_ticket {id}` followed by a newline.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- `api_state/tickets.json` contains exactly one ticket.
- The ticket has component `checkout`, priority `P1`, and labels `bug` and `checkout`.
- `api_state/calls.log` records one create call.
- Do not modify `bug_report.md`.

Keep the work local to this repository. Do not use network access.

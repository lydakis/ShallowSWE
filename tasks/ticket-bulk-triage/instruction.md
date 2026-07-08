# Bulk Triage Existing Tickets

Apply the triage policy to the existing records in `api_state/tickets.json`. Do not create tickets.

Policy:

- Priority precedence is evaluated in this order:
  1. `P0` when severity is `critical` or labels contain `security`.
  2. `P1` when severity is `high` or product area is `checkout` or `billing`.
  3. `P3` when severity is `low` or type is `docs`.
  4. `P2` otherwise.
- Owner is:
  - `security` when labels contain `security`.
  - `payments` when product area is `checkout` or `billing`.
  - `support` when type is `docs`.
  - `platform` otherwise.
- Every ticket must have a `triaged` label.
- Preserve existing nonempty labels, add `triaged`, remove duplicates, and sort labels alphabetically.
- Update only tickets whose `priority`, `owner`, or `labels` change.
- Write `api_state/calls.log` with one line per changed ticket, sorted by ticket id:
  `update_ticket <id> priority=<priority> owner=<owner> labels=<comma-separated-labels>`
- If no tickets change, write an empty `api_state/calls.log`.
- Ticket count and ids must remain unchanged.

Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.

Keep the work local to this repository. Do not use network access.

# Apply Webhook Idempotency Everywhere

Imports already skip duplicate event IDs, but webhook and replay paths do not. Make all entry points share idempotency.

## Acceptance Criteria

- Duplicate event IDs are ignored through import, webhook, and replay.
- Totals change once per unique event.
- Processed event IDs preserve first-seen order.

Keep the work local to this repository. Do not use network access.

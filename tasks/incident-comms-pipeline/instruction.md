The local incident communications command needs to reconcile statuspage-style component,
incident, and subscriber-notification state from a deterministic timeline.

Run shape:

```sh
python -m incident_comms.cli \
  --timeline <timeline.json> \
  --state <state.json> \
  --output-state <output.json> \
  --audit-log <audit.jsonl>
```

Inputs:

- `timeline.json`: timeline events plus stale incident keys to resolve.
- `state.json`: deterministic local statuspage state.

State fields:

- `components`: object keyed by component name, with status values such as `operational`,
  `degraded`, `partial_outage`, and `major_outage`.
- `incidents`: array of incident objects.
- `subscribers`: object keyed by subscriber ID. Each subscriber has `components` and
  `minimum_severity`.
- `notification_queue`: array of already-enqueued notification objects.
- `next_incident_number`: next integer used to create IDs as `INC-<number>`.
- `call_log`: array maintained by the local API.

Incident fields:

- `id`
- `incident_key`
- `title`
- `status`: `investigating`, `identified`, `monitoring`, or `resolved`
- `components`: array of component names.
- `updates`: array of update objects with `update_key`, `at`, `status`, and `message`.

Notification fields:

- `notification_key`
- `subscriber_id`
- `kind`: `component_status` or `incident_update`
- `target`: component name for component notifications, incident ID for incident notifications
- `at`
- `severity`
- `message`

Timeline fields:

- `events`: array sorted by the command, not by input order.
- `stale_incident_keys`: incident keys that should be resolved if still active after timeline
  events are processed.
- `stale_resolution_at`: timestamp to use for stale-resolution updates.

Event fields:

- `sequence`: integer tie-breaker.
- `at`: ISO timestamp string.
- `type`: one of `component_status`, `incident_opened`, `incident_update`, `incident_resolved`.
- `component`: component name for `component_status`.
- `component_status`: new component status for `component_status`.
- `incident_key`: stable incident key for incident events.
- `title`: incident title for `incident_opened`.
- `status`: incident status after the update.
- `components`: array of component names affected by the incident.
- `update_key`: stable update key.
- `message`: update message.
- `severity`: `low`, `medium`, `high`, or `critical` for incident events.

Rules:

- Process `events` by `at` ascending, then `sequence` ascending.
- For `component_status`, update the component only if the status changes.
- Component status changes have derived severities: `operational` = `low`, `degraded` =
  `medium`, `partial_outage` = `high`, and `major_outage` = `critical`.
- For incident events, match existing incidents by `incident_key`.
- If an incident event references a missing incident, create it before posting the event update.
- New incident IDs are `INC-<next_incident_number>`, then increment `next_incident_number`.
- `incident_opened` creates or reopens the incident with status `investigating`.
- `incident_update` sets the incident status to the event's `status`.
- `incident_resolved` sets the incident status to `resolved`.
- Incident `components` are the union of existing components and event components, sorted
  alphabetically.
- Post an update only when its `update_key` is not already present on that incident.
- Preserve existing updates and never duplicate an `update_key`.
- After all timeline events, resolve every incident in `stale_incident_keys` that exists and is not
  already resolved. Add one update with update_key `stale-resolve:<incident_key>`, `at` equal to
  `stale_resolution_at`, status `resolved`, and message `Resolved as stale after reconciliation`.
  Use `low` as the notification severity for stale-resolution notifications; do not add a
  `severity` field to incident update objects.
- Subscriber component matching is based on the subscriber's `components`. `["*"]` matches every
  component. Otherwise, a subscriber matches when at least one subscribed component is affected.
- A subscriber receives a notification only when the event severity is greater than or equal to
  the subscriber's `minimum_severity`. Severity order is `low`, `medium`, `high`, `critical`.
- For each component status change, enqueue one `component_status` notification for each matching
  subscriber in subscriber ID order. The notification key is
  `component:<component>:<at>:<sequence>:<subscriber_id>`. The message is
  `<component> is <component_status>`.
- For each newly posted incident update, enqueue one `incident_update` notification for each
  subscriber whose component subscription intersects the incident's reconciled component list.
  Use subscriber ID order. The notification key is `incident:<update_key>:<subscriber_id>`.
  The notification message is the update message.
- Existing `notification_key` values are never duplicated.
- Do not delete incidents, updates, or components.
- Use the local API methods for state changes so `call_log` records one call per actual mutation
  and no calls for unchanged data.
- Re-running the command against an already reconciled state should produce no state changes and a
  single `noop` audit row.

The audit log is JSONL. Write one object per logical action with exactly these keys:

- `action`
- `target`
- `detail`

Allowed `action` values:

- `component_status`
- `create_incident`
- `post_update`
- `resolve_stale`
- `enqueue_notification`
- `noop`

Ordering is part of the contract: audit rows must follow processing order. For a missing incident,
write `create_incident` before its first `post_update`. Component status audit rows occur at the
event position where the status changed. Notification audit rows occur immediately after the
state change that enqueued them.

Keep the existing CLI module and package name. Do not use network access.

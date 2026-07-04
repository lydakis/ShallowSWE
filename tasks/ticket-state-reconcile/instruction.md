The local ticket sync command needs to reconcile a desired manifest against API-side ticket state.

Run shape:

```sh
python -m ticket_sync.cli \
  --manifest <manifest.json> \
  --state <state.json> \
  --output-state <output.json> \
  --audit-log <audit.jsonl>
```

Inputs:

- `manifest.json`: array of desired ticket objects.
- `state.json`: local deterministic API state.

Manifest ticket fields:

- `external_key`: stable source key.
- `title`
- `owner`
- `severity`
- `desired_status`: `open` or `closed`.
- `labels`: array of strings.

State ticket fields:

- `id`
- `external_key`
- `title`
- `owner`
- `severity`
- `status`
- `labels`
- `archived`
- optional `duplicate_of`

Rules:

- Match manifest rows to existing tickets by normalized `external_key`.
- Normalized keys are stripped and lowercased.
- Ignore archived tickets when matching.
- If no non-archived ticket exists, create a new ticket.
- New ticket IDs use the next integer after the largest existing `TKT-<number>` ID.
- If exactly one non-archived ticket exists, update it in place.
- If multiple non-archived tickets match, keep the lowest numeric ticket ID as canonical and mark
  every later matching ticket as `duplicate` with `duplicate_of` set to the canonical ID.
- After duplicate cleanup, reconcile the canonical ticket to the manifest fields.
- Use the manifest spelling of `external_key` on the canonical ticket after reconciliation.
- `desired_status=open` means the canonical ticket should be `open`. If it was `closed`, reopen it.
- `desired_status=closed` means the canonical ticket should be `closed`. If it was `open`, close it.
- Preserve existing tickets that are not mentioned by the manifest.
- Preserve archived duplicate tickets without changing them.
- Do not delete tickets.
- If the local API raises `TransientTicketError`, retry that same API action once before failing.

The audit log is JSONL. Write one object per action in manifest order, with exactly these keys:

- `action`
- `ticket_id`
- `external_key`
- `detail`

Allowed action values:

- `create`
- `update`
- `reopen`
- `close`
- `dedupe`
- `retry`
- `noop`

Write `retry` before the retried action succeeds. Write `dedupe` once for each duplicate ticket
that is marked duplicate. Write `noop` only when the canonical ticket already matches the manifest
and no duplicate cleanup was needed for that manifest row.

The command must write both `output-state` and `audit-log`.

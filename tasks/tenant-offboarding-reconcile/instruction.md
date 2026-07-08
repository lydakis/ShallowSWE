# Reconcile Tenant Offboarding Runbook

Implement an idempotent offboarding reconciler in `scripts/process_offboarding.py`.

The script must support:

```bash
python scripts/process_offboarding.py
python scripts/process_offboarding.py --state-dir /path/to/state --output /path/to/output
```

The verifier runs the script twice on the visible state and on fresh hidden states. The second run
must not change any state, duplicate calls, or duplicate audit entries.

## Inputs

All input files live under `state/` unless `--state-dir` is supplied:

- `runbook.json`: object with `run_date` and `requests`. A request has `request_id`, `tenant_id`,
  `status`, `scheduled_for`, and `requested_by`.
- `tenants.json`: `tenant_id`, `name`, `status`, `owner_user_id`, `region`.
- `memberships.json`: `membership_id`, `tenant_id`, `user_id`, `role`, `status`, `user_type`.
- `sessions.json`: `session_id`, `tenant_id`, `user_id`, `status`.
- `api_keys.json`: `key_id`, `tenant_id`, `owner_type`, `status`.
- `invites.json`: `invite_id`, `tenant_id`, `status`.
- `exports.json`: `export_id`, `tenant_id`, `status`, `retention_until`.
- `tickets.json`: `ticket_id`, `tenant_id`, `status`, `assignee`, `tags`.
- `integrations.json`: `integration_id`, `tenant_id`, `kind`, `status`.
- `billing_accounts.json`: `billing_id`, `tenant_id`, `status`, `invoice_state`,
  `collection_lock`.
- `legal_holds.json`: `hold_id`, `tenant_id`, `status`, `preserve_exports`, `reason`.
- `call_log.json`: existing operation records.
- `audit_log.json`: existing audit summary records.

## Eligible Requests

Process requests where:

- `status` is `approved` or `in_progress`
- `scheduled_for <= run_date`

Ignore requests already `completed` and requests scheduled after `run_date`.

Process eligible requests sorted by `scheduled_for`, then `tenant_id`, then `request_id`.

## Workflow Rules

For each eligible request, apply these phases in order. Within each phase, sort targets by their ID.
Append call-log rows only for operations that actually changed state and are not already present.

The unique operation key is `(request_id, tenant_id, action, target_id)`. If a call-log row with
that key already exists, do not append another one.

When appending a call-log row, include exactly:

- `request_id`
- `tenant_id`
- `action`
- `target_id`
- `sequence`

`sequence` is one plus the current maximum sequence in `call_log.json`.

### Phase 1: Mark Tenant

If the tenant is neither `offboarding`, `hold_review`, nor `closed`, set `status` to
`offboarding` and append action `mark_offboarding` with target ID equal to the tenant ID.

### Phase 2: Revoke Access

- For active sessions for the tenant, set `status` to `revoked` and append `revoke_session` using
  `session_id`.
- For active API keys for the tenant, set `status` to `disabled` and append `disable_api_key` using
  `key_id`.
- For pending invites for the tenant, set `status` to `canceled` and append `cancel_invite` using
  `invite_id`.
- For active non-owner memberships for the tenant, set `status` to `disabled` and append
  `disable_membership` using `membership_id`. The owner membership stays active.

### Phase 3: Quiesce Integrations

For integrations for the tenant, sorted by `integration_id`:

- For `webhook` and `scim` integrations with `status == "active"`, set `status` to `disabled`
  and append `disable_integration` using `integration_id`.
- For `custom_domain` integrations with `status == "verified"`:
  - if the tenant has an active legal hold, set `status` to `hold_review` and append
    `review_domain` using `integration_id`;
  - otherwise set `status` to `parked` and append `park_domain` using `integration_id`.
- Integrations already in `disabled`, `hold_review`, or `parked` status are unchanged.

### Phase 4: Lock Billing

For billing accounts for the tenant, sorted by `billing_id`:

- If `status == "active"` and the tenant has an active legal hold, set `status` to `locked_hold`
  and append `hold_billing` using `billing_id`.
- If `status == "active"` and the tenant does not have an active legal hold, set `status` to
  `closed` and append `close_billing` using `billing_id`.
- If `invoice_state` is `open` or `past_due`, ensure `collection_lock == true`. If this changes
  the row, append `lock_collections` using `billing_id`.

### Phase 5: Queue Tickets

For each open ticket for the tenant, ensure `assignee` is `success-ops` and the tag `offboarding`
is present exactly once. If either changed, append `queue_ticket` using `ticket_id`.

### Phase 6: Settle Exports

An active legal hold is a row for the tenant where `status == "active"`.

- If there is an active legal hold with `preserve_exports == true`, set `running` or `requested`
  exports to `retained_hold` and append `retain_export` using `export_id`.
- Otherwise, set `running` or `requested` exports to `canceled` and append `cancel_export`.
- For `complete` exports with `retention_until < run_date`, set `status` to `expired` and append
  `expire_export`.

### Phase 7: Finalize

- If the tenant has an active legal hold, set tenant `status` to `hold_review`.
- Otherwise, set tenant `status` to `closed`.
- Append `finalize_tenant` with target ID equal to the final tenant status only when the status
  changed in this phase.
- Set the request `status` to `completed` and add `completed_at = run_date`.
- Append `complete_request` with target ID equal to the request ID only when the request status or
  completed date changed.

## Audit and Summary

After each request is processed, ensure exactly one audit entry exists for
`audit_id = "<request_id>:summary"`. The audit entry must contain exactly:

- `audit_id`
- `request_id`
- `tenant_id`
- `final_status`
- `active_legal_hold`
- `changed_operations`

`changed_operations` is the number of call-log rows for that request and tenant after processing.

Write `output/offboarding_summary.json` containing exactly:

- `processed_requests`
- `closed_tenants`
- `hold_review_tenants`
- `revoked_sessions`
- `disabled_api_keys`
- `canceled_invites`
- `disabled_memberships`
- `disabled_integrations`
- `parked_domains`
- `domain_reviews`
- `closed_billing_accounts`
- `held_billing_accounts`
- `collection_locks`
- `queued_tickets`
- `retained_exports`
- `canceled_exports`
- `expired_exports`
- `call_log_entries`

Counts are computed after processing. `processed_requests` counts requests with
`status == "completed"` and `completed_at == run_date`. The operation counts are counts of
call-log entries by action. `held_billing_accounts` counts `hold_billing` operations.

Write JSON files deterministically with sorted object keys and two-space indentation.
Record order in state files is not semantically meaningful, except that `call_log.json` must reflect
operation sequence through its `sequence` values and must not contain duplicate operation keys.

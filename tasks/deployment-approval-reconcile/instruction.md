The deployment coordinator needs to reconcile a desired rollout plan against local API state.

Run shape:

```sh
python -m deploy_ops.cli \
  --plan <plan.json> \
  --state <state.json> \
  --output-state <output.json> \
  --audit-log <audit.jsonl>
```

Input state fields:

- `services`: map from service name to service state.
- `call_log`: array of local API calls.

Each service has:

- `rings`: map from ring name to currently deployed version.
- `history`: array of deployment/block records.

Plan fields:

- `now`: ISO timestamp.
- `ring_order`: ordered array of ring names.
- `deployments`: ordered array of desired deployments.
- `approvals`: array of approval records.
- `checks`: array of health-check records.
- `freeze_windows`: array of freeze-window records.

Deployment fields:

- `service`
- `target_version`
- `rings`: rings to reconcile for that service.
- `required_checks`: map from ring to required check names.
- `approval_required_for`: array of rings that require approval.

Rules:

- Process deployments in plan order.
- Process each deployment's rings in `ring_order`, skipping rings not listed on that deployment.
- A ring is already satisfied when its current version equals `target_version`.
- A ring may deploy only when every earlier listed ring for the same deployment is satisfied.
- A ring may deploy only when every required check for `(service, target_version, ring)` has
  result `pass`.
- A ring listed in `approval_required_for` may deploy only when an approval exists for
  `(service, target_version, ring)` with `approved: true`.
- A ring may not deploy when `plan.now` falls inside a freeze window for that service/ring.
  Freeze windows are inclusive of `start` and exclusive of `end`.
- If a ring cannot deploy, write exactly one `blocked` audit row for that ring and stop processing
  later rings for that deployment.
- Do not mutate unrelated services or rings.
- Do not delete history or call-log entries.
- Re-running against an already reconciled or already blocked state must not duplicate history.

Audit log rows are JSONL with exactly these keys:

- `action`
- `service`
- `ring`
- `detail`

Allowed `action` values:

- `deploy`
- `already_current`
- `blocked`
- `noop`

Audit rows follow deployment/ring processing order. Use:

- `deploy` when a ring is newly moved to the target version.
- `already_current` when a listed ring already has the target version.
- `blocked` when checks, approval, freeze, or prior-ring ordering prevents deployment.
- `noop` only when a listed deployment has no newly deployed, already-current, or blocked rings.

For `blocked.detail`, use the first reason in this priority order:

1. `prior_ring_not_deployed:<ring>`
2. `freeze_window`
3. `missing_approval`
4. `failed_check:<check>`
5. `missing_check:<check>`

For `deploy.detail`, use the target version.
For `already_current.detail`, use the target version.
For `noop.detail`, use `no changes`.

Keep the existing CLI module and package name. Do not use network access.

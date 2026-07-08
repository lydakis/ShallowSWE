# Build SDK Migration Readiness Package

Create deterministic migration-readiness artifacts under `output/` by reconciling the repository
files under `catalog/`, `owners/`, `dependencies/`, `configs/`, `repos/`, `ci/`, `incidents/`,
`migration/`, and `advisories/`.

Implement the transformation in `scripts/build_migration_readiness.py`. The verifier reruns it on
the visible repository and on fresh hidden repositories. Keep the work local to this repository and
do not use network access.

The script must support:

```bash
python scripts/build_migration_readiness.py
python scripts/build_migration_readiness.py --root /path/to/repo --output /path/to/repo/output
```

## Inputs

- `catalog/services.json`: array of service objects with `service_id`, `name`, `team`, `tier`, and
  `runtime`.
- `owners/teams.csv`: `team,manager,slack,email`.
- `dependencies/packages.csv`: `service_id,package,current_version,target_version,scope,critical`.
  Use the row where `package == "payments-sdk"` for the service.
- `configs/<service_id>.json`: object with `feature_flags`, `deployment_strategy`, and
  `allow_legacy_webhooks`.
- `repos/<service_id>/...`: service source files. Scan `.py`, `.js`, `.ts`, and `.go` files.
- `ci/<service_id>.log`: text log. `STATUS=pass` or `STATUS=fail` defines CI status. The token
  `LEGACY_CONTRACT_TEST_FAILED` marks a contract-test blocker.
- `incidents/incidents.csv`: `service_id,date,severity,status`. Count only open `P0` and `P1`
  incidents.
- `migration/exceptions.csv`: `service_id,expires_on,reason,approver`. An exception is active when
  `expires_on >= report_date`.
- `migration/waves.json`: object with `report_date` and `waves`. Each wave has `service_id`,
  `wave`, `freeze_start`, `freeze_end`, and `cutover_deadline`.
- `advisories/*.md`: Markdown files with frontmatter keys `package`, `affected_below`, `severity`,
  and `action`.

## Output Files

Write exactly these files under `output/`:

- `migration_readiness.json`
- `team_rollup.csv`
- `migration_board.md`
- `summary.json`

## Shared Rules

- Sort service rows by `service_id`.
- Sort team rows by `team`.
- Sort markdown board rows by `service_id`.
- Write JSON deterministically with sorted object keys.
- Version comparison is semantic numeric comparison over dot-separated integer parts.
- A service is in a freeze window when `report_date` is from `freeze_start` through `freeze_end`
  inclusive.
- `legacy_api_count` is the total occurrence count across scanned source files of these tokens:
  - `LegacyPaymentClient`
  - `legacy_charge(`
  - `legacy_refund(`
  - `verify_webhook_legacy(`
  - `post_legacy_ledger(`
- `ci_status` is `fail` when the service log contains `STATUS=fail`; otherwise it is `pass`.
- `open_incidents` counts open incidents whose severity is `P0` or `P1`.
- `exception_active` is true when at least one exception row for the service has
  `expires_on >= report_date`.
- `expired_exception` applies when the service has an exception row but no active exception and at
  least one other blocker.
- `security_advisory` applies when a critical advisory for `payments-sdk` exists and the service's
  `current_version` is below the advisory `affected_below` version.

Evaluate blockers in this exact order:

1. `legacy_api_usage` when `legacy_api_count > 0`
2. `ci_failed` when `ci_status == "fail"`
3. `contract_test_failed` when the CI log contains `LEGACY_CONTRACT_TEST_FAILED`
4. `open_incident` when `open_incidents > 0`
5. `migration_flag_disabled` when `payments_sdk_v4` is not in `feature_flags`
6. `frozen_cutover` when the service is currently in its freeze window
7. `expired_exception` using the rule above
8. `security_advisory` using the rule above

Map blockers to actions in the same order:

- `legacy_api_usage`: `remove legacy payment API calls`
- `ci_failed`: `fix failing migration CI`
- `contract_test_failed`: `repair contract fixtures`
- `open_incident`: `resolve active incident`
- `migration_flag_disabled`: `enable payments_sdk_v4 flag`
- `frozen_cutover`: `move cutover outside freeze window`
- `expired_exception`: `renew or close expired exception`
- `security_advisory`: `upgrade payments-sdk before migration`

For `migration_readiness.json`, `actions` is exactly the list of actions derived from blockers. If
`blockers` is empty, `actions` must be an empty list. The phrase `schedule cutover` is used only in
`migration_board.md` for ready rows with no blocker-derived action.

Compute `readiness`:

- `blocked` when blockers include any of `ci_failed`, `contract_test_failed`, `open_incident`,
  `frozen_cutover`, `expired_exception`, or `security_advisory`
- `exception` when `exception_active == true` and all blockers are only from
  `legacy_api_usage` and `migration_flag_disabled`
- `needs_work` when blockers are non-empty and the service is not `blocked` or `exception`
- `ready` when blockers are empty

## `migration_readiness.json`

Top-level key is exactly `services`. Each row has exactly:

- `service_id`
- `name`
- `team`
- `tier`
- `runtime`
- `current_version`
- `target_version`
- `wave`
- `cutover_deadline`
- `readiness`
- `blockers`
- `actions`
- `legacy_api_count`
- `ci_status`
- `open_incidents`
- `exception_active`

## `team_rollup.csv`

Columns are exactly:

`team,manager,slack,email,services,ready,needs_work,blocked,exceptions,legacy_api_count,open_incidents,highest_tier`

`services` is a semicolon-separated list of service IDs owned by the team, sorted alphabetically.
`highest_tier` is the minimum numeric tier among owned services, or blank when the team owns none.

## `migration_board.md`

Write exactly this structure:

```md
# SDK Migration Board

## Blocked
<items>

## Needs Work
<items>

## Ready
<items>

## Exceptions
<items>
```

Item lines are:

`- <service_id> [<team>] blockers=<semicolon blockers or none> action=<first action or schedule cutover>`

If a section has no items, write exactly `- none`.

## `summary.json`

Top-level keys are exactly:

- `services`
- `ready`
- `needs_work`
- `blocked`
- `exceptions`
- `legacy_api_count`
- `open_incidents`
- `teams`
- `waves`

Definitions:

- `services`: number of service rows.
- `ready`, `needs_work`, `blocked`, and `exceptions`: counts of services in each readiness state.
- `legacy_api_count`: sum of service `legacy_api_count`.
- `open_incidents`: sum of service `open_incidents`.
- `teams`: number of owner-team rows in `owners/teams.csv`.
- `waves`: number of distinct wave names, not the number of service-wave rows.

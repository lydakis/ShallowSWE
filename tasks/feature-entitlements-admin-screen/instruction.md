# Feature Entitlements Admin Screen

You are working in a Python static web-rendering app. The existing app renders routes through:

```bash
python -m workspace_app.cli --route /accounts --data-dir fixtures/visible --output /tmp/out.html
```

Add a new entitlements admin area that integrates with the existing app instead of creating a separate script.

## Required Product Behavior

- Register route `/entitlements`.
- Register route `/entitlements/overrides`.
- Add a primary navigation item with label `Entitlements` and href `/entitlements`.
- Add `workspace_app/screens/entitlements.py`.
- Add `workspace_app/screens/entitlement_overrides.py`.
- Add `workspace_app/selectors/entitlements.py`.
- Preserve the existing routes `/`, `/accounts`, `/support`, `/billing`, and `/reports`.
- Add a regression test under `tests/` that is discovered by `python -m unittest discover -s tests` and exercises both `/entitlements` and `/entitlements/overrides`.

The new route reads the same `--data-dir` used by the CLI. The data directory contains:

- `workspaces.json`: list of workspaces with `workspace_id`, `name`, `owner`, and `plan`.
- `subscriptions.json`: object with `report_date` and `subscriptions`; each subscription has `workspace_id`, `status`, and `renewal_date`.
- `plan_features.json`: object keyed by plan. Each plan contains feature keys with `enabled` and `limit`. A `null` limit means unlimited.
- `usage.json`: list of usage records with `workspace_id`, `feature`, and `current_usage`.
- `overrides.json`: list of manual overrides with `workspace_id`, `feature`, `enabled`, `expires_on`, and `reason`.

Render one entitlement row for every workspace and every feature present in `plan_features.json`. A manual override is active only when `expires_on >= report_date`. Expired overrides must be ignored. If multiple active overrides exist for the same workspace and feature, use the one with the latest `expires_on`.

## Entitlement Calculation

For each workspace-feature row:

- `effective_enabled` starts from the workspace plan's feature `enabled` value.
- If an active override exists, its `enabled` value replaces the plan value.
- `limit` comes from the workspace plan's feature `limit`; render `unlimited` for `null`.
- `usage` comes from `usage.json`; use `0` when no usage row exists.
- A subscription is serviceable only when its `status` is `active` or `trialing`.
- `override_days_remaining` is `expires_on - report_date` in whole days when an active override exists; otherwise it is blank.

Compute `status` with this priority order:

1. `blocked` if the subscription is not serviceable.
2. `blocked` if `effective_enabled` is false.
3. `over_limit` if `limit` is numeric and `usage > limit`.
4. `override_review` if an active override exists and `override_days_remaining <= 14`.
5. `ok` otherwise.

Compute `recommended_action` with the same priority:

1. Not serviceable subscription: `Restore subscription`
2. Disabled effective entitlement: `Review feature access`
3. Usage over numeric limit: `Contact owner about limit`
4. Active override expiring within 14 days: `Review temporary override`
5. Otherwise: `Monitor`

Compute `reason_codes` as a comma-separated list in this exact order, or `none` when empty. Join multiple codes with a literal comma and no spaces, for example `subscription_not_serviceable,usage_over_limit`.

1. `subscription_not_serviceable` when the subscription is not serviceable
2. `feature_disabled` when `effective_enabled` is false
3. `usage_over_limit` when usage is over a numeric limit
4. `override_expiring` when an active override expires within 14 days

Sort rows by:

1. status severity: `blocked`, then `over_limit`, then `override_review`, then `ok`
2. workspace owner ascending
3. workspace name ascending
4. feature ascending

## Required HTML Contract

The rendered page must include:

- `<main data-screen="entitlements">`
- an `<h1>` whose text is exactly `Entitlements`
- metrics with `data-metric` keys:
  - `workspaces`
  - `blocked`
  - `over-limit`
  - `overrides-expiring`
- a table with `data-table="feature-entitlements"`
- one table row per workspace-feature pair with `data-workspace-id="<workspace_id>"` and `data-feature="<feature>"`
- cells in each row with `data-field` keys:
  - `workspace`
  - `owner`
  - `plan`
  - `feature`
  - `effective_enabled`
  - `limit`
  - `usage`
  - `status`
  - `override_days_remaining`
  - `reason_codes`
  - `recommended_action`

Metric values should be plain numeric text. The element that has a `data-metric` attribute should have text content equal to the numeric value only.

Render boolean cell values as lowercase `true` or `false`. This applies to the main screen's `effective_enabled` cell and the override screen's `enabled` cell.

Metric definitions:

- `workspaces`: number of workspaces.
- `blocked`: number of entitlement rows whose status is `blocked`.
- `over-limit`: number of entitlement rows whose status is `over_limit`.
- `overrides-expiring`: number of entitlement rows whose status is `override_review`.

## Required Override Review Screen

The `/entitlements/overrides` route must include:

- `<main data-screen="entitlement-overrides">`
- an `<h1>` whose text is exactly `Entitlement Overrides`
- metrics with `data-metric` keys:
  - `active-overrides`
  - `expiring-overrides`
  - `expired-overrides`
- a table with `data-table="entitlement-overrides"`
- one row per active override with `data-workspace-id="<workspace_id>"` and `data-feature="<feature>"`
- cells in each row with `data-field` keys:
  - `workspace`
  - `owner`
  - `feature`
  - `enabled`
  - `days_remaining`
  - `status`
  - `reason`

For the override screen, active overrides are the same non-expired overrides used by the main screen, after applying the latest-`expires_on` rule for duplicate workspace-feature overrides. Sort active override rows by `days_remaining` ascending, then workspace owner ascending, then workspace name ascending, then feature ascending. Override row `status` is `expiring` when `days_remaining <= 14`, otherwise `active`. `expired-overrides` counts expired override records before duplicate collapsing.

# Build Repository Observability Coverage Audit

Create deterministic observability audit artifacts under `output/` by reconciling route metadata,
source telemetry, dashboards, alerts, incidents, owners, temporary exemptions, downstream service
edges, runbook freshness, and recent deployment rollback readiness in this repository.

Implement the transformation in `scripts/build_observability_audit.py`. The verifier reruns it on
the visible repository and on fresh hidden repositories. Keep the work local to this repository and
do not use network access.

The script must support:

```bash
python scripts/build_observability_audit.py
python scripts/build_observability_audit.py --root /path/to/repo --output /path/to/repo/output
```

## Inputs

- `catalog/services.json`: array of services with `service_id`, `display_name`, `team`, `tier`,
  and `language`.
- `catalog/routes.csv`: `route_id,service_id,method,path,handler,tier_override,pii_expected`.
  Use `tier_override` when present; otherwise use the owning service tier.
- `owners/teams.csv`: `team,manager,slack,pagerduty`.
- `policies/coverage_rules.json`: `report_date`, `required_events`, `dashboard_required_tier`,
  `paging_alert_required_tier`, `runbook_required_tier`, `runbook_review_days`,
  `trace_edge_required_tier`, `deploy_recency_days`, `pii_tokens`, and `due_days`.
- `services/<service_id>/src/...`: source files. Scan `.py`, `.js`, `.ts`, `.tsx`, and `.go`
  files.
- `dashboards/*.json`: each file has `panels`, where a panel may include `route_id`.
- `alerts/*.yaml`: simple YAML-like alert files. An alert item has `route_id` and `severity`.
  Only `severity: page` is a paging alert.
- `incidents/incidents.csv`: `route_id,date,severity,status`. Count only open `P0` and `P1`
  incidents.
- `exemptions/observability_exemptions.csv`: `route_id,control,expires_on,reason`. An exemption is
  active when `expires_on >= report_date`.
- `dependencies/route_edges.csv`: `source_route_id,target_service_id,critical`. A critical edge
  from a route at or above `trace_edge_required_tier` must have route-specific source evidence that
  names both the target service and `downstream_trace_id`.
- `runbooks/route_runbooks.json`: array of `route_id`, `url`, and `reviewed_on`. A route at or
  above `runbook_required_tier` needs a runbook whose `reviewed_on` is no older than
  `runbook_review_days` before `report_date`.
- `deployments/recent_deploys.csv`: `service_id,deployed_at,commit,changed_routes,rollback_ready`.
  A deploy is relevant to a route when `service_id` matches, `deployed_at` is within
  `deploy_recency_days` before `report_date`, and `changed_routes` contains the route ID or `*`.

## Output Files

Write exactly these files under `output/`:

- `route_observability.json`
- `owner_gaps.csv`
- `observability_board.md`
- `remediation_plan.csv`
- `summary.json`

## Shared Rules

- Numeric tiers are ordered by criticality: tier `1` is more critical than tier `2`, and tier `2`
  is more critical than tier `3`. A route is at or above a threshold when `tier <= threshold`.
- Sort route rows by `route_id`.
- Sort owner/team rows by `team`.
- Sort markdown board rows by `route_id`.
- Write JSON deterministically with sorted object keys.
- `evidence_files` are source file paths relative to the repository root. Include source files that
  mention the route ID, sorted lexicographically.
- For a route, evaluate telemetry only on source lines inside its `evidence_files` that also mention
  that route ID. Do not let one route borrow events, trace context, or PII tokens from another route
  in the same file.
- `missing_events` is the required events from `policies/coverage_rules.json` that do not appear in
  those route-specific source lines, preserving policy order.
- `trace_context` is missing when no route-specific source line contains `trace_id`.
- `pii_safe` is missing when `pii_expected` is false and any configured PII token appears in route
  specific source line. PII tokens are case-sensitive substring checks.
- `has_dashboard` is true when any dashboard panel names the route ID.
- `has_paging_alert` is true when any alert item names the route ID with `severity: page`.
- A dashboard panel is required when `tier <= dashboard_required_tier`.
- A paging alert is required when `tier <= paging_alert_required_tier`.
- A current runbook is required when `tier <= runbook_required_tier`. Routes above that numeric
  threshold must report `runbook_status = "not_required"` even when they have no runbook row.
- Downstream trace propagation is required only for critical edges whose source route has
  `tier <= trace_edge_required_tier`.
- Active exemptions apply only to missing controls. They do not suppress open incidents, and they do
  not suppress `pii_safe`.

Evaluate missing controls in this exact order:

1. `request_started`
2. `request_succeeded`
3. `request_failed`
4. `trace_context`
5. `pii_safe`
6. `dashboard_panel`
7. `paging_alert`
8. `runbook_current`
9. `downstream_trace`
10. `rollback_ready`

Map controls to actions in the same order:

- `request_started`: `add request_started telemetry`
- `request_succeeded`: `add request_succeeded telemetry`
- `request_failed`: `add request_failed telemetry`
- `trace_context`: `propagate trace_id in telemetry`
- `pii_safe`: `remove PII fields from telemetry`
- `dashboard_panel`: `add dashboard panel`
- `paging_alert`: `add paging alert`
- `runbook_current`: `refresh route runbook`
- `downstream_trace`: `propagate trace_id to downstream service`
- `rollback_ready`: `add rollback plan for recent deploy`

For each route:

- `raw_missing_controls` is the ordered list before applying exemptions.
- `exempted_controls` is the ordered list of active exemptions that matched missing controls,
  excluding `pii_safe`.
- `missing_controls` is `raw_missing_controls` minus `exempted_controls`.
- `open_incidents` counts open `P0` and `P1` incidents for the route.
- `status` is:
  - `blocked` when `open_incidents > 0`, or `pii_safe` is in `missing_controls`, or tier 1 is
    missing `paging_alert`, or a route with a relevant recent deploy is missing `rollback_ready`.
  - `accepted_risk` when `raw_missing_controls` is non-empty, `missing_controls` is empty, and
    `open_incidents == 0`.
  - `needs_work` when `missing_controls` is non-empty.
  - `ready` when none of the above apply.

## `route_observability.json`

Top-level key is exactly `routes`. Each row has exactly:

- `route_id`
- `service_id`
- `method`
- `path`
- `team`
- `tier`
- `status`
- `missing_controls`
- `exempted_controls`
- `missing_events`
- `has_dashboard`
- `has_paging_alert`
- `evidence_files`
- `open_incidents`
- `pii_leaks`
- `runbook_status`
- `trace_edge_gaps`
- `recent_deploys`
- `rollback_ready`

`pii_leaks` is the sorted list of configured PII tokens present in route evidence when
`pii_expected` is false. It is empty otherwise.
`runbook_status` is one of `current`, `stale`, `missing`, or `not_required`.
`trace_edge_gaps` is the sorted list of target service IDs for critical downstream edges missing
route-specific downstream trace propagation.
`recent_deploys` is the count of relevant recent deploy rows. `rollback_ready` is false when any
relevant recent deploy has `rollback_ready=false`; otherwise true.

## `owner_gaps.csv`

Columns are exactly:

`team,manager,slack,pagerduty,routes,ready,needs_work,blocked,accepted_risk,missing_controls,open_incidents,runbook_gaps,trace_edge_gaps,rollback_gaps,highest_tier`

`routes` is a semicolon-separated list of route IDs owned by the team, sorted alphabetically.
`missing_controls` is the total non-exempt missing controls across those routes. `highest_tier` is
the minimum numeric tier among owned routes, or blank when the team owns none.
`runbook_gaps`, `trace_edge_gaps`, and `rollback_gaps` count routes for that team with the
corresponding non-exempt missing control.

## `observability_board.md`

Write exactly this structure:

```md
# Observability Coverage Board

## Blocked
<items>

## Needs Work
<items>

## Accepted Risk
<items>

## Ready
<items>
```

Item lines are:

`- <route_id> [<team>] missing=<semicolon missing controls or none> action=<first action or resolve open incident or monitor>`

Use `resolve open incident` when the route has open incidents and no missing-control action comes
first. Use `monitor` only when there is no missing control and no open incident. If a section has no
items, write exactly `- none`.

## `remediation_plan.csv`

Columns are exactly:

`route_id,team,priority,due_date,actions,evidence`

Include every route whose status is not `ready`, sorted by `priority` then `route_id`. Priority is:

- `P0` when the route is blocked because of an open incident, `pii_safe`, or tier-1 missing
  `paging_alert`.
- `P1` when the route is blocked for any other reason.
- `P2` when the route status is `needs_work`.
- `P3` when the route status is `accepted_risk`.

`due_date` is `report_date` plus the number of days from `due_days[status]`. Use ISO dates.
`actions` is a semicolon-separated list: `resolve open incident` first when present, followed by
mapped missing-control actions in control order. For accepted risk with no remaining missing
controls, use `monitor accepted exemption`.
`evidence` is a semicolon-separated list of source evidence files followed by `deploy:<commit>` for
relevant recent deploys and `runbook:<url>` when a runbook exists. Keep the list sorted within each
kind and omit empty kinds.

## `summary.json`

Top-level keys are exactly:

- `routes`
- `ready`
- `needs_work`
- `blocked`
- `accepted_risk`
- `services`
- `teams`
- `missing_controls`
- `open_incidents`
- `tier1_blocked`
- `dashboard_gaps`
- `paging_alert_gaps`
- `runbook_gaps`
- `trace_edge_gaps`
- `rollback_gaps`
- `recent_deploys`

Definitions:

- `routes`: number of route rows.
- `ready`, `needs_work`, `blocked`, and `accepted_risk`: counts of routes in each state.
- `services`: number of services in `catalog/services.json`.
- `teams`: number of owner rows in `owners/teams.csv`.
- `missing_controls`: sum of non-exempt missing controls across routes.
- `open_incidents`: sum of route open-incident counts.
- `tier1_blocked`: number of tier 1 routes with status `blocked`.
- `dashboard_gaps`: number of routes with non-exempt `dashboard_panel` missing.
- `paging_alert_gaps`: number of routes with non-exempt `paging_alert` missing.
- `runbook_gaps`: number of routes with non-exempt `runbook_current` missing.
- `trace_edge_gaps`: number of routes with non-exempt `downstream_trace` missing.
- `rollback_gaps`: number of routes with non-exempt `rollback_ready` missing.
- `recent_deploys`: total relevant recent deploy rows across routes.

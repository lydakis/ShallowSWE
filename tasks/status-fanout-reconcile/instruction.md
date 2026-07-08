# Reconcile Build Status Fanout

Reconcile CI build results into three local API state files:

- `api_state/statuses.json`
- `api_state/deployment_gates.json`
- `api_state/notifications.json`

Also write:

- `api_state/calls.log`
- `api_state/release_summary.json`

Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
Keep the work local to this repository. Do not use network access.

## Inputs

Read `input/build_results.json`. Each result has:

- `commit`
- `project`
- `suite`
- `branch`
- `owner`
- `passed`
- `failed`: array of failed test names
- `flaky`: array of flaky test names
- `blocking`: boolean
- `environments`: array of deployment environments affected by the result

Read `input/release_rules.json`. It has:

- `report_time`: timestamp string copied to the summary and gate rows
- `context_prefix`: prefix for status contexts
- `protected_branches`: branches that page owners on failed blocking results
- `required_suites`: map of project to environment to required suite names
- `owner_channels`: map of owner to notification channel
- `default_channel`: notification channel when an owner is not mapped

State files may already contain unrelated rows. Preserve unrelated rows.

## Status Reconciliation

For each build result, compute a desired status:

- `commit`: copied from the build result
- `context`: `<context_prefix>/<project>/<suite>`
- `state`: `failure` when `failed` is nonempty, otherwise `success`
- `body`:
  - failure: `<project> <suite> failed on <commit>: <failed tests joined by ", ">`
  - success with flaky tests: `<project> <suite> passed on <commit>: <passed> checks; flaky: <flaky tests joined by ", ">`
  - success without flaky tests: `<project> <suite> passed on <commit>: <passed> checks`

Reconcile `api_state/statuses.json`:

- Match existing statuses by `commit` and `context`.
- If an identical status already exists, do not write a status call.
- If a matching status exists but any of `state` or `body` differs, update that status.
- If no matching status exists, append a new status.
- Sort the final status array by `commit`, then `context`.

## Deployment Gate Reconciliation

For every unique `(project, environment, commit)` mentioned by the build results, compute a desired
deployment gate. The suites required for a gate come from
`required_suites[project][environment]`.

Gate fields are exactly:

- `project`
- `environment`
- `commit`
- `state`
- `blockers`
- `updated_at`

Rules:

- `updated_at` is `release_rules.report_time`.
- If a required suite has no build result for the same project and commit, add
  `missing:<suite>` to `blockers`.
- If a required suite has a nonempty `failed` array, add `failed:<suite>` to `blockers`.
- If a required suite has a nonempty `flaky` array and `blocking` is true, add
  `flaky:<suite>` to `blockers`.
- Preserve blocker order by the required suite order from `release_rules.json`, and within a suite
  use `failed` before `flaky`.
- `state` is `blocked` when `blockers` is nonempty, otherwise `ready`.

Reconcile `api_state/deployment_gates.json`:

- Match existing gates by `project`, `environment`, and `commit`.
- If an identical gate already exists, do not write a gate call.
- If a matching gate exists but any of `state`, `blockers`, or `updated_at` differs, update it.
- If no matching gate exists, append it.
- Sort the final gate array by `project`, then `environment`, then `commit`.

## Notification Reconciliation

Append notifications to `api_state/notifications.json` only when a notification with the same
`key` does not already exist. Notification rows have exactly:

- `key`
- `channel`
- `owner`
- `kind`
- `summary`

Create result notifications for each build result where:

- `branch` is in `protected_branches`
- `blocking` is true
- `failed` is nonempty

Result notification:

- `key`: `result:<commit>:<project>:<suite>:failure`
- `channel`: `owner_channels[owner]`, or `default_channel`
- `owner`: copied from the build result
- `kind`: `result_failure`
- `summary`: `<project>/<suite> failed on protected branch <branch> for <commit>`

Create gate notifications for each desired deployment gate where:

- `environment` is `prod`
- `state` is `blocked`

Gate notification:

- `key`: `gate:<project>:<environment>:<commit>:blocked`
- `channel`: channel for the first owner found in build-result order for that project and commit,
  or `default_channel` if none exists or the owner is unmapped
- `owner`: first owner found in build-result order for that project and commit, or `unassigned`
- `kind`: `gate_blocked`
- `summary`: `<project> <environment> blocked for <commit>: <blockers joined by ", ">`

Sort final notifications by `key`.

## Calls Log

Write `api_state/calls.log` from scratch on every run. It contains one line per changed desired
status, changed desired gate, or newly appended notification.

Call lines are ordered in three groups:

1. Status calls in build-result order:
   - `update_status <commit> <context> <state>`
   - `post_status <commit> <context> <state>`
2. Gate calls in sorted final desired-gate order:
   - `update_gate <project> <environment> <commit> <state>`
   - `post_gate <project> <environment> <commit> <state>`
3. Notification calls in sorted notification-key order for newly appended notifications:
   - `notify <key>`

If nothing changes, write an empty `api_state/calls.log`.

## Summary

Write `api_state/release_summary.json` with exactly:

- `generated_at`: `release_rules.report_time`
- `results_seen`: number of build results
- `status_updates`: number of status `post_status` or `update_status` calls
- `gate_updates`: number of gate `post_gate` or `update_gate` calls
- `notifications_sent`: number of newly appended notifications
- `failed_results`: number of build results with nonempty `failed`
- `blocked_gates`: number of desired gates whose state is `blocked`
- `ready_gates`: number of desired gates whose state is `ready`
- `projects_with_blocked_prod`: sorted unique projects with a blocked desired `prod` gate

The operation must be idempotent. Re-running after a successful run should preserve state and write
an empty calls log, except `release_summary.json` should still reflect the current zero changed-call
counts for that replay.

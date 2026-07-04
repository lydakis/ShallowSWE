# Post Build Status

Read `build_result.json` and write exactly one status update to the mock API state.

Write `api_state/statuses.json` as a JSON array containing exactly one object with these fields:

- `body`: the failure or success body described below.
- `commit`: the `commit` value from the build result.
- `context`: `ci/{suite}` from the build result.
- `state`: `failure` when `failed` has entries, otherwise `success`.
- Failure body: `{project} {suite} failed on {commit}: {failed tests joined by ", "}`.
- Success body: `{project} {suite} passed on {commit}: {passed} tests`.

Write `api_state/calls.log` as exactly this line: `post_status {commit} ci/{suite} {state}` followed
by a newline.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- `api_state/statuses.json` contains one status with fields `body`, `commit`, `context`, and `state`.
- State is `failure`, commit is `abc1234`, and the body names failing tests.
- Call log records one post.
- Do not modify `build_result.json`.

Keep the work local to this repository. Do not use network access.

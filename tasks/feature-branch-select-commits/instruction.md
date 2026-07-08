# Select Feature Branch Commits

Apply only the commits marked bugfix and test from `commits/` into `repo/`. Omit telemetry and experimental config commits.

## Acceptance Criteria

- Selected commits are `c1-bugfix` and `c3-test`.
- Write `selected_commits.txt` at the repository root with exactly:
  ```text
  c1-bugfix
  c3-test
  ```
- `repo/app.py` contains the bug fix.
- `repo/app.py` exposes `should_retry(status_code)`.
- `should_retry` returns true for HTTP status codes `408`, `429`, and all `5xx` codes.
- `should_retry` returns false for `400`.
- `repo/tests/test_app.py` exists.
- Telemetry and experimental config files are absent.

Keep the work local to this repository. Do not use network access.

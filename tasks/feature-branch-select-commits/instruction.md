# Select Feature Branch Commits

Apply only the commits marked bugfix and test from `commits/` into `repo/`. Omit telemetry and experimental config commits.

## Acceptance Criteria

- Selected commits are `c1-bugfix` and `c3-test`.
- `repo/app.py` contains the bug fix.
- `repo/tests/test_app.py` exists.
- Telemetry and experimental config files are absent.

Keep the work local to this repository. Do not use network access.

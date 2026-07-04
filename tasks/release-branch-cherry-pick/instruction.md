# Apply Release Note Fix To Release Branch

The fixture simulates a release branch. Apply only `patches/9f1-release-note.json` to `repo/` and record it in `applied_commits.txt`.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- `branch.txt` remains `release/1.4`.
- Release notes include the migration note.
- Only `9f1-release-note` is recorded.
- Experimental files are absent.

Keep the work local to this repository. Do not use network access.

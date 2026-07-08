# Apply Release Note Fix To Release Branch

The fixture simulates a release branch. Apply only release-note patch files from `patches/` to `repo/` and record the applied patch IDs in `applied_commits.txt`. A release-note patch is any patch whose `id` contains `release-note`.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- Preserve the existing `branch.txt` content exactly.
- Apply release-note patches by appending each patch's `append` text to `repo/<file>`.
- Do not apply experimental patches or create experimental files.
- Record exactly the applied release-note patch IDs, one per line, in `applied_commits.txt`.
- The script must work for any release branch name and any release-note patch ID, not only the visible fixture.
- Experimental files are absent.

Keep the work local to this repository. Do not use network access.

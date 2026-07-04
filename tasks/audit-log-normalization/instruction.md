# Normalize Audit Logs

Read `input/audit.log` and write normalized audit rows, rejects, and a summary under `output/`. Normalize actions to lowercase snake case.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Normalized rows are sorted by timestamp and actor.
- Malformed rows are captured in rejects.
- Summary counts rows by action.

Keep the work local to this repository. Do not use network access.

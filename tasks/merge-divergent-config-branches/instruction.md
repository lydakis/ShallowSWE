# Merge Divergent Config Branches

The fixture simulates main, release, and feature config branches. Produce `repo/config.json` by merging release and feature into main.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- Region is `us-east`.
- `enable_new_checkout` is true and timeout is 45.
- Merge report records both sources and the timeout conflict.

Keep the work local to this repository. Do not use network access.

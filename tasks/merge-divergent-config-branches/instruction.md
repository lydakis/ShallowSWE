# Merge Divergent Config Branches

The fixture simulates main, release, and feature config branches. Produce `repo/config.json` by merging release and feature into main.

## Acceptance Criteria

- Implement the operation in `scripts/apply_task.py`; the verifier reruns it on fresh local state.
- For the visible fixture, region is `us-east`.
- For the visible fixture, `enable_new_checkout` is true and timeout is 45.
- Merge report records both sources and the timeout conflict.
- Write the merged config to `repo/config.json`.
- Write `merge_report.json` with exactly these keys:
  - `resolved_conflicts`: an array containing `retry_timeout_seconds`.
  - `sources`: an array containing `release` followed by `feature`.
- Preserve feature flags from the feature branch, including any additional flags present in hidden inputs.
- For `retry_timeout_seconds`, choose the release branch value when release and feature diverge.

Keep the work local to this repository. Do not use network access.

# Merge Divergent Config Branches

The fixture simulates main, release, and feature config branches. Produce `repo/config.json` by merging release and feature into main.

Merge semantics are deterministic:

- Start from the complete main config, preserving main-only top-level keys and feature flags.
- Overlay all release top-level keys and release feature flags onto main.
- Overlay all feature-branch entries under `features` after release, preserving additional flags.
- The feature branch does not override other top-level release values.
- `retry_timeout_seconds` is a reported conflict when release and feature differ, and the release
  value wins even when it is not the largest value.

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
- Preserve main-only and release-only configuration while applying feature flags.

Keep the work local to this repository. Do not use network access.

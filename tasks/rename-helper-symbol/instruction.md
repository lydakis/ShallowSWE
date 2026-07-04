# Rename Helper Symbol

Rename `format_user_key` to `format_user_id` across the package. Keep behavior the same and remove the old public helper name.

## Acceptance Criteria

- `helpers.format_user_id` exists.
- `app.describe_user` uses the new helper.
- The old helper name is no longer exported.

Keep the work local to this repository. Do not use network access.

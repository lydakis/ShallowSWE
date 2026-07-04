# Add User Export Name Field

The user export needs a new `name` field. Add it to JSON and CSV output while preserving the old `display_name` field.

## Acceptance Criteria

- JSON and CSV include both `name` and `display_name`.
- CSV field order is `id,email,name,display_name`.
- Existing display names remain unchanged.

Keep the work local to this repository. Do not use network access.

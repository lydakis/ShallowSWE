# Invalidate Settings Cache On Change

Feature flags are cached by path and stay stale after the file changes. Invalidate when contents change while keeping per-file isolation.

## Acceptance Criteria

- Changed files return changed flags.
- Separate files do not contaminate each other.
- Repeated unchanged reads still work.

Keep the work local to this repository. Do not use network access.
